from __future__ import annotations

import os
import json
import traceback
import tempfile
import subprocess

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from core.supabase import supabase

router = APIRouter()

AUDIO_BUCKET = os.getenv("SUPABASE_AUDIO_BUCKET", "pab_audio")


def get_audio_duration_seconds(
    audio_bytes: bytes, suffix: str = ".webm"
) -> float | None:
    """
    Uses ffprobe to detect audio duration.
    Returns None if duration cannot be determined.
    """
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            temp_path = tmp.name

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                temp_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)
        duration = data.get("format", {}).get("duration")

        if duration is None:
            return None

        return round(float(duration), 2)

    except Exception:
        return None

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@router.get("/")
async def list_cases():
    try:
        response = (
            supabase.table("cases")
            .select("*, pab_beneficiaries(*)")
            .not_.is_("transcript_raw", None)
            .not_.is_("sbar_json", None)
            .not_.is_("triage_flags", None)
            .not_.is_("recommended_actions", None)
            .neq("triage_flags", "{}")
            .neq("recommended_actions", "{}")
            .order("opened_at", desc=True)
            .execute()
        )

        items = []

        for row in response.data:
            beneficiary = row.pop("pab_beneficiaries", {})
            merged = {**row, **beneficiary}
            items.append(merged)

        return {"items": items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/audio")
async def create_case_from_audio(
    button_id: str = Form(...),
    audio: UploadFile = File(...),
):
    try:
        # 1) Validate beneficiary by button_id
        beneficiary_res = (
            supabase.table("pab_beneficiaries")
            .select("*")
            .eq("button_id", button_id)
            .single()
            .execute()
        )

        beneficiary = beneficiary_res.data
        if not beneficiary:
            raise HTTPException(
                status_code=404,
                detail="Beneficiary not found for button_id",
            )

        # 2) Read uploaded audio
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # 3) Pre-generate case_id so storage path and case row match
        case_id = str(uuid4())

        file_ext = "webm"
        if audio.filename and "." in audio.filename:
            file_ext = audio.filename.rsplit(".", 1)[-1].lower()

        file_suffix = f".{file_ext}"
        storage_path = f"{button_id}/{case_id}/raw.{file_ext}"

        # 4) Calculate duration before upload
        audio_duration_seconds = get_audio_duration_seconds(
            audio_bytes=audio_bytes,
            suffix=file_suffix,
        )

        # 5) Upload audio to Supabase Storage
        supabase.storage.from_(AUDIO_BUCKET).upload(
            path=storage_path,
            file=audio_bytes,
            file_options={
                "content-type": audio.content_type or "audio/webm",
                "upsert": "false",
            },
        )

        # 6) Insert case row
        now_iso = datetime.now(timezone.utc).isoformat()

        case_payload = {
            "case_id": case_id,
            "nric": beneficiary["nric"],
            "button_id": button_id,
            "status": "new",
            "urgency_bucket": "requires_review",
            "queue_score": 60,
            "source": "pab_audio",
            "transcript_raw": None,
            "transcript_english": None,
            "audio_caption_text": None,
            "sbar_json": {
                "situation": "PAB audio received",
                "background": f"Patient: {beneficiary['full_name']}",
                "assessment": "Awaiting AI transcription and audio analysis",
                "recommendation": "Place into review queue",
            },
            "triage_flags": [
                "audio_received",
                "low_confidence_ai",
            ],
            "recommended_actions": [
                "call_patient_now",
                "inform_emergency_contact",
            ],
            "audio_file_url": storage_path,
            "audio_duration_seconds": audio_duration_seconds,
            "audio_uploaded_at": now_iso,
        }

        case_res = supabase.table("cases").insert(case_payload).execute()
        case_row = case_res.data[0] if case_res.data else None

        return {
            "message": "Audio uploaded and case created",
            "case": case_row,
            "beneficiary": {
                "nric": beneficiary["nric"],
                "full_name": beneficiary["full_name"],
                "primary_language": beneficiary.get("primary_language"),
                "address": beneficiary.get("address"),
                "unit_number": beneficiary.get("unit_number"),
                "phone_number": beneficiary.get("phone_number"),
                "emergency_contact_name": beneficiary.get("emergency_contact_name"),
                "emergency_contact": beneficiary.get("emergency_contact"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
