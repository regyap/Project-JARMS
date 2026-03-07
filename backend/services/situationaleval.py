# services/asr.py
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException


async def mock_transcribe_audio(audio_bytes: bytes) -> str:
    return "Mock transcript: resident sounds distressed and mentions chest pain."


async def get_pab_beneficiary_by_nric(nric: str) -> Optional[Dict[str, Any]]:
    try:
        from core.supabase import supabase  # lazy import

        response = (
            supabase.table("pab_beneficiaries")
            .select("*")
            .eq("nric", nric)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return response.data[0]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch beneficiary: {e}")


async def process_audio_and_lookup_beneficiary(
    audio_bytes: bytes,
    nric: str,
) -> Dict[str, Any]:
    transcript = await mock_transcribe_audio(audio_bytes)
    beneficiary = await get_pab_beneficiary_by_nric(nric)

    return {
        "transcript": transcript,
        "beneficiary": beneficiary,
    }
