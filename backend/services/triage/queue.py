from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List


POLICY_PATH = Path(__file__).resolve().parents[2] / "policy.json"


def load_policy() -> Dict[str, Any]:
    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def get_elapsed_seconds(case_row: Dict[str, Any]) -> float:
    """
    Prefer audio_uploaded_at, fall back to opened_at.
    """
    start_dt = parse_iso_datetime(case_row.get("audio_uploaded_at"))
    if not start_dt:
        start_dt = parse_iso_datetime(case_row.get("opened_at"))

    if not start_dt:
        return 0.0

    now_dt = datetime.now(timezone.utc)
    elapsed = (now_dt - start_dt).total_seconds()
    return max(elapsed, 0.0)


def normalize_bucket(raw_bucket: Optional[str], policy: Dict[str, Any]) -> str:
    allowed = set(policy.get("urgency_buckets", []))
    bucket = (raw_bucket or "").strip()

    if bucket not in allowed:
        return "requires_review"

    return bucket


def bucket_base_score(bucket: str) -> int:
    score_map = {
        "life_threatening": 100,
        "emergency": 80,
        "requires_review": 60,
        "minor_emergency": 40,
        "non_emergency": 20,
    }
    return score_map.get(bucket, 60)


def compute_queue_score(
    case_row: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Live queue score = bucket base score + waiting pressure.
    Uses audio_uploaded_at/opened_at + policy target_wait_seconds.
    """
    policy = policy or load_policy()

    urgency_bucket = normalize_bucket(case_row.get("urgency_bucket"), policy)

    # force top priority immediately
    if urgency_bucket == "life_threatening":
        return 100

    base_score = bucket_base_score(urgency_bucket)
    target_wait_seconds = policy.get("target_wait_seconds", {}).get(urgency_bucket) or 0

    elapsed_seconds = get_elapsed_seconds(case_row)

    if target_wait_seconds <= 0:
        progress = 1.0
    else:
        progress = elapsed_seconds / float(target_wait_seconds)

    waiting_pressure = min(progress, 2.0) * 20

    # optional small modifier if transcript is still missing
    transcript_modifier = 5 if not case_row.get("transcript_raw") else 0

    score = base_score + waiting_pressure + transcript_modifier
    return min(int(round(score)), 100)


def enrich_case_with_live_queue_score(
    case_row: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy = policy or load_policy()

    enriched = dict(case_row)
    enriched["urgency_bucket"] = normalize_bucket(
        enriched.get("urgency_bucket"), policy
    )
    enriched["live_queue_score"] = compute_queue_score(enriched, policy)
    enriched["elapsed_seconds"] = round(get_elapsed_seconds(enriched), 1)
    enriched["target_wait_seconds"] = policy.get("target_wait_seconds", {}).get(
        enriched["urgency_bucket"]
    )

    return enriched


def sort_cases_for_queue(
    cases: List[Dict[str, Any]],
    policy: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    policy = policy or load_policy()

    enriched = [enrich_case_with_live_queue_score(case, policy) for case in cases]

    return sorted(
        enriched,
        key=lambda c: (
            -c["live_queue_score"],
            c.get("opened_at") or "",
        ),
    )
