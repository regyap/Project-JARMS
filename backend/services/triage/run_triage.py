"""
services/triage/run_triage.py
===================
Backend-friendly parallel AI pipeline for Project JARMS.

Purpose:
  1. Fetch audio from Supabase Storage using the stored audio_file_url path
  2. Run 3 AI services in parallel:
      - pureadio
      - situationeval
      - captioner
  3. Run final triage (with beneficiary context)
  4. Update the corresponding row in `cases`
"""

from __future__ import annotations

import os
import time
import json
import tempfile
import traceback
import concurrent.futures
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from core.supabase import supabase
from services.triage import pureadio, situationeval, captioner, stt_triage
from services.triage.queue import (
    load_policy,
    normalize_bucket,
    compute_queue_score,
)

load_dotenv()

AUDIO_BUCKET = os.getenv("SUPABASE_AUDIO_BUCKET", "pab_audio")
TEST_AUDIO_PATH = os.getenv("TEST_AUDIO_PATH", "interviewcoolies.mp3")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _get_elapsed_seconds(case_row: Dict[str, Any]) -> float:
    """Prefer audio_uploaded_at, fall back to opened_at."""
    start_dt = _parse_iso_datetime(case_row.get("audio_uploaded_at"))
    if not start_dt:
        start_dt = _parse_iso_datetime(case_row.get("opened_at"))
    if not start_dt:
        return 0.0
    now_dt = datetime.now(timezone.utc)
    elapsed = (now_dt - start_dt).total_seconds()
    return max(elapsed, 0.0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(data: Any) -> Any:
    try:
        json.dumps(data)
        return data
    except Exception:
        return {"raw": str(data)}


def _bucket_base_score(bucket: str) -> int:
    score_map = {
        "life_threatening": 100,
        "emergency": 80,
        "requires_review": 60,
        "minor_emergency": 40,
        "non_emergency": 20,
    }
    return score_map.get(bucket, 60)


def _normalize_recommended_actions(
    raw_actions: Any,
    urgency_bucket: str,
    policy: Dict[str, Any],
) -> list[str]:
    actions: list[str] = []

    if isinstance(raw_actions, list):
        actions = [str(a).strip() for a in raw_actions if str(a).strip()]
    elif isinstance(raw_actions, str):
        if "," in raw_actions:
            actions = [a.strip() for a in raw_actions.split(",") if a.strip()]
        else:
            lines = [
                line.strip(" -1234567890.)\t") for line in raw_actions.splitlines()
            ]
            actions = [line.strip() for line in lines if line.strip()]
    elif isinstance(raw_actions, dict):
        primary = raw_actions.get("primary_action")
        secondary = raw_actions.get("secondary_actions", [])
        if primary:
            actions.append(str(primary).strip())
        if isinstance(secondary, list):
            actions.extend(str(a).strip() for a in secondary if str(a).strip())

    # Validate against allowed actions from policy
    allowed = policy.get("allowed_actions", [])
    if allowed:
        actions = [a for a in actions if a in allowed]

    if not actions:
        actions = policy.get("recommended_primary_actions_by_bucket", {}).get(
            urgency_bucket,
            ["call_patient_now", "inform_emergency_contact"],
        )

    deduped = []
    seen = set()
    for action in actions:
        if action and action not in seen:
            deduped.append(action)
            seen.add(action)

    return deduped


def _set_case_status(
    case_id: str,
    status: str,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    payload = {"status": status, "updated_at": _now_iso()}
    if extra_fields:
        payload.update(extra_fields)
    supabase.table("cases").update(payload).eq("case_id", case_id).execute()


def _download_audio_from_supabase(storage_path: str) -> bytes:
    try:
        data = supabase.storage.from_(AUDIO_BUCKET).download(storage_path)
        if not data:
            raise ValueError(f"No file returned for storage path: {storage_path}")
        return data
    except Exception as e:
        raise RuntimeError(f"Failed to download audio from Supabase: {e}") from e


def _get_case_by_audio_path(storage_path: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("cases")
            .select("*")
            .eq("audio_file_url", storage_path)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        return res.data[0]
    except Exception as e:
        raise RuntimeError(f"Failed to fetch case by audio path: {e}") from e


def _load_context_for_case(case_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load beneficiary context including language preferences and
    medical summary from pab_beneficiaries.
    """
    nric = case_row.get("nric")
    beneficiary = None

    if nric:
        try:
            res = (
                supabase.table("pab_beneficiaries")
                .select("*")
                .eq("nric", nric)
                .limit(1)
                .execute()
            )
            if res.data:
                beneficiary = res.data[0]
        except Exception:
            beneficiary = None

    primary_language = "unknown"
    secondary_language = None
    patient_medical_summary = None

    if beneficiary:
        primary_language = beneficiary.get("primary_language") or "unknown"
        secondary_language = beneficiary.get("secondary_language")

        # Build patient medical summary from beneficiary record
        patient_medical_summary = {
            "age": beneficiary.get("age"),
            "medical_conditions": beneficiary.get("medical_conditions") or [],
            "medications": beneficiary.get("medications") or [],
            "allergies": beneficiary.get("allergies") or [],
            "mobility_status": beneficiary.get("mobility_status"),
        }

    return {
        "nric": nric,
        "beneficiary": beneficiary,
        "primary_language": primary_language,
        "secondary_language": secondary_language,
        "patient_medical_summary": patient_medical_summary,
    }


def _flatten_triage_flags(raw_flags: Any) -> list[str]:
    """
    Convert triage_flags to a JSON array for Supabase.

    The LLM returns a dict of booleans, e.g. {"not_breathing": true, ...}.
    The DB column expects a JSON array of the flag names that are true,
    e.g. ["not_breathing", "fall_detected_or_suspected"].
    If the input is already a list, pass it through.
    """
    if isinstance(raw_flags, dict):
        return [k for k, v in raw_flags.items() if v]
    if isinstance(raw_flags, list):
        return raw_flags
    return []


def _normalize_triage_output(
    case_row: Dict[str, Any],
    stt_result: Dict[str, Any],
    triage_result: Dict[str, Any],
    situation_eval: Dict[str, Any],
    caption_result: Dict[str, Any],
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    transcript_raw = stt_result.get("raw_transcript")
    transcript_english = stt_result.get("transcript")

    audio_caption_text = (
        caption_result.get("caption")
        or caption_result.get("description")
        or caption_result.get("text")
        or str(caption_result)
    )

    raw_bucket = triage_result.get("urgency_bucket") or triage_result.get("bucket")
    urgency_bucket = normalize_bucket(raw_bucket, policy)

    recommended_actions = _normalize_recommended_actions(
        triage_result.get("recommended_actions") or triage_result.get("actions"),
        urgency_bucket,
        policy,
    )

    sbar_json = _safe_json(
        triage_result.get("sbar")
        or {
            "situation": "AI triage completed for uploaded PAB audio.",
            "background": f"Case {case_row.get('case_id')}, NRIC {case_row.get('nric')}.",
            "assessment": f"Urgency bucket: {urgency_bucket}.",
            "recommendation": "Review recommended actions and place into queue.",
        }
    )

    temp_case_row = {
        **case_row,
        "urgency_bucket": urgency_bucket,
    }
    queue_score = compute_queue_score(temp_case_row, policy)

    return {
        "status": "queued",
        "urgency_bucket": urgency_bucket,
        "queue_score": queue_score,
        "transcript_raw": transcript_raw,
        "transcript_english": transcript_english,
        "audio_caption_text": audio_caption_text,
        "triage_flags": _flatten_triage_flags(triage_result.get("triage_flags")),
        "recommended_actions": recommended_actions,
        "sbar_json": sbar_json,
        "updated_at": _now_iso(),
    }


# ------------------------------------------------------------
# Main pipeline
# ------------------------------------------------------------


def run_pipeline(storage_path: str) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("🚀 PROJECT JARMS — BACKEND PIPELINE STARTING")
    print(f"   Storage Path : {storage_path}")
    print("=" * 60)

    start_time = time.time()
    policy = load_policy()

    case_row = _get_case_by_audio_path(storage_path)
    if not case_row:
        raise RuntimeError(f"No case found for audio_file_url={storage_path}")

    case_id = case_row["case_id"]
    print(f"[INIT] Found case_id={case_id}")

    _set_case_status(case_id, "processing")

    context = _load_context_for_case(case_row)
    triage_protocol = stt_triage.load_triage_protocol()

    primary_language = context["primary_language"]
    secondary_language = context["secondary_language"]
    patient_medical_summary = context["patient_medical_summary"]

    print(
        f"[INIT] Protocol loaded. Primary language: {primary_language}, "
        f"Secondary language: {secondary_language}, "
        f"Medical summary available: {patient_medical_summary is not None}"
    )

    print("[FETCH] Downloading audio from Supabase Storage...")
    audio_bytes = _download_audio_from_supabase(storage_path)

    ext = os.path.splitext(storage_path)[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(audio_bytes)
        temp_audio_path = tmp.name

    print(f"[FETCH] Audio written to temp file: {temp_audio_path}")

    try:
        print("[PARALLEL] Spawning AI workers (pureadio, situationeval, captioner)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            start_pureadio = time.time()
            future_pureadio = executor.submit(pureadio.run, temp_audio_path)

            start_situeval = time.time()
            future_situeval = executor.submit(situationeval.run, temp_audio_path)

            start_caption = time.time()
            future_caption = executor.submit(captioner.run, temp_audio_path)

            print("[PARALLEL] Waiting for all AI services to complete...")
            res_pureadio = future_pureadio.result() or {}
            print(
                f"[PARALLEL] pureadio finished in {time.time() - start_pureadio:.2f}s"
            )

            res_situeval = future_situeval.result() or {}
            print(
                f"[PARALLEL] situationeval finished in {time.time() - start_situeval:.2f}s"
            )

            res_caption = future_caption.result() or {}
            print(
                f"[PARALLEL] captioner finished in {time.time() - start_caption:.2f}s"
            )

            print(f"[DEBUG] res_pureadio keys: {list(res_pureadio.keys())}")
            print(f"[DEBUG] res_situeval keys: {list(res_situeval.keys())}")
            print(f"[DEBUG] res_caption keys: {list(res_caption.keys())}")

        raw_tx = res_pureadio.get("raw_transcript") or ""
        stt_result = {
            "raw_transcript": raw_tx,
            "transcript": res_pureadio.get("translation") or "NO_TRANSLATION",
            "primary_language": primary_language,
            "secondary_language": secondary_language,
            "silence_detected": "SILENCE_DETECTED" in raw_tx,
        }

        print("[TRIAGE] Running final urgency classification with enriched context...")
        triage_result = stt_triage.run_triage(
            transcript=stt_result["transcript"],
            protocol=triage_protocol,
            situation_eval=res_situeval,
            caption=res_caption,
            primary_language=primary_language,
            secondary_language=secondary_language,
            patient_medical_summary=patient_medical_summary,
        )

        try:
            stt_triage.print_summary(stt_result, triage_result)
        except Exception:
            pass

        print("[DB] Updating case row in Supabase...")
        update_payload = _normalize_triage_output(
            case_row=case_row,
            stt_result=stt_result,
            triage_result=triage_result,
            situation_eval=res_situeval,
            caption_result=res_caption,
            policy=policy,
        )

        update_res = (
            supabase.table("cases")
            .update(update_payload)
            .eq("case_id", case_id)
            .execute()
        )

        total_time = time.time() - start_time
        print(f"\n✅ Pipeline complete in {total_time:.2f}s.")

        return {
            "case_id": case_id,
            "storage_path": storage_path,
            "policy_name": policy.get("policy_name"),
            "stt_result": stt_result,
            "situation_eval": res_situeval,
            "caption": res_caption,
            "triage_result": triage_result,
            "db_update": update_res.data,
            "runtime_seconds": round(total_time, 2),
        }

    except Exception as e:
        _set_case_status(case_id, "error")
        raise e

    finally:
        try:
            os.remove(temp_audio_path)
        except Exception:
            pass


async def run_pipeline_from_storage_path(storage_path: str) -> Dict[str, Any]:
    return run_pipeline(storage_path)


if __name__ == "__main__":
    try:
        result = run_pipeline(TEST_AUDIO_PATH)
        print(json.dumps(result, indent=2, default=str))
    except KeyboardInterrupt:
        print("\n[ABORT] Pipeline stopped by user.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Pipeline crashed: {e}")
        traceback.print_exc()
