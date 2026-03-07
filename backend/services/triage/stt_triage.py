import json
import os
import re
from pathlib import Path
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv
from core.supabase import supabase as _supabase_client

load_dotenv()

# -----------------------------
# CONFIG
# -----------------------------

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "YOUR_DASHSCOPE_KEY")
SUPABASE_URL      = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY      = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

USER_ID = int(os.getenv("USER_ID", "1"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

TRIAGE_MODEL         = "qwen3-235b-a22b"
# Always resolve the protocol relative to this module's directory
TRIAGE_PROTOCOL_FILE = str(Path(__file__).parent / "triage_protocol.md")

# -----------------------------
# CLIENT
# -----------------------------

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# -----------------------------
# LANGUAGE MAPPING
# -----------------------------

LANGUAGE_MAP = {
    "english": "English",
    "chinese": "Chinese",
    "mandarin": "Chinese",
    "hokkien": "Chinese",
    "teochew": "Chinese",
    "cantonese": "Chinese",
    "malay": "Malay",
    "tamil": "Tamil",
    "spanish": "Spanish",
    "japanese": "Japanese"
}

# -----------------------------
# HELPERS
# -----------------------------

def load_triage_protocol(filepath: str = TRIAGE_PROTOCOL_FILE) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def get_user_language(user_id: int) -> str:
    try:
        data = (
            _supabase_client.table("users")
            .select("preferred_language")
            .eq("id", user_id)
            .execute()
        )
        if not data.data:
            return "English"
        user_lang = data.data[0]["preferred_language"].lower()
        return LANGUAGE_MAP.get(user_lang, "English")
    except Exception as e:
        print(f"[WARN] Could not fetch user language: {e}. Defaulting to English.")
        return "English"

# -----------------------------
# LLM Triage
# -----------------------------

def run_triage(transcript: str, stt_confidence: float, protocol: str, situation_eval: Optional[dict] = None, caption: Optional[dict] = None) -> dict:
    """Run triage analysis using qwen3-235b-a22b."""
    transcript = transcript or "NO_SPEECH_DETECTED"
    silence_note = ""
    if "SILENCE_DETECTED" in transcript or stt_confidence < 0.2:
        silence_note = "\n[SYSTEM NOTE: Audio contained silence or was too poor to transcribe.]"

    situation_str = ""
    if situation_eval:
        severity     = situation_eval.get("severity") or "unknown"
        high_risk    = situation_eval.get("high_risk_triggers") or []
        impairment   = situation_eval.get("impairment_signals") or []
        environmental = situation_eval.get("environmental_cues") or []
        reasoning    = situation_eval.get("reasoning") or "No reasoning provided."
        situation_str = f"""
=== SITUATION EVALUATION (NON-VERBAL SIGNALS) ===
- Severity: {severity}
- High-Risk Triggers: {', '.join(high_risk) if isinstance(high_risk, list) else high_risk}
- Impairment Signals: {', '.join(impairment) if isinstance(impairment, list) else impairment}
- Environmental Cues: {', '.join(environmental) if isinstance(environmental, list) else environmental}
- Signal Reasoning: {reasoning}
"""

    caption_str = ""
    if caption:
        description = caption.get("caption") or "No caption provided."
        conf        = caption.get("confidence") or 0
        notable     = caption.get("notable_events") or []
        caption_str = f"""
=== AUDIO CAPTION (AI INTERPRETATION) ===
- Description: {description}
- Confidence: {conf}
- Notable Events: {', '.join(notable) if isinstance(notable, list) else notable}
"""

    system_prompt = f"""You are an AI triage assistant for Project JARMS — a 24/7 emergency monitoring service for elderly residents living alone in Singapore.

=== TRIAGE PROTOCOL ===
{protocol}
=== END PROTOCOL ===

CRITICAL RULES:
1. Prioritize ACOUSTIC/SITUATION SIGNALS over transcription if they conflict.
2. Always follow the classification rules in order.
3. Return ONLY a valid JSON object. No markdown fences.

Return JSON with keys:
- urgency: "life_threatening" | "emergency" | "urgent" | "non_urgent" | "no_triage_needed"
- reasoning: concise explanation
- recommended_action: specific next steps
- pab_flags: list of strings
"""

    user_prompt = f"""Analyse these PAB audio inputs:

{situation_str}
{caption_str}

TRANSCRIPT:
{transcript}
{silence_note}
"""

    try:
        response = client.chat.completions.create(
            model=TRIAGE_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            extra_body={"enable_thinking": False},
            temperature=0.1
        )
        raw_output = response.choices[0].message.content
        cleaned    = re.sub(r"```(?:json)?\s*|\s*```", "", raw_output).strip()
        result     = json.loads(cleaned)
        result["raw_output"] = raw_output
        return result
    except Exception as e:
        print(f"[TRIAGE] Error: {e}")
        return {
            "urgency": "urgent",
            "reasoning": f"Triage processing failed: {e}",
            "recommended_action": "Manual operator intervention required.",
            "pab_flags": ["triage_failure"]
        }

def save_to_supabase(user_id: int, audio_file: str, stt_result: dict, triage_result: dict, situation_eval: Optional[dict] = None, caption: Optional[dict] = None):
    if DRY_RUN:
        print("[DB] Dry run enabled. Skipping Supabase write.")
        return
    try:
        flags = triage_result.get("pab_flags") or []
        if not isinstance(flags, list):
            flags = [str(flags)]
        if stt_result.get("silence_detected"):
            flags.append("silence_detected")

        payload = {
            "user_id":            user_id,
            "audio_url":          audio_file,
            "raw_transcript":     stt_result.get("transcript"),
            "stt_confidence":     stt_result.get("confidence"),
            "urgency":            triage_result.get("urgency"),
            "reasoning":          triage_result.get("reasoning"),
            "recommended_action": triage_result.get("recommended_action"),
            "pab_flags":          list(set(flags)),
            "language_detected":  stt_result.get("language_detected"),
            "situation_eval":     situation_eval,
            "caption_eval":       caption,
        }
        _supabase_client.table("triage_history").insert(payload).execute()
        print("[DB] Result saved to triage_history.")
    except Exception as e:
        print(f"[DB] Error saving to Supabase: {e}")

def print_summary(stt: dict, triage: dict):
    print("\n" + "="*60)
    print("🚑 PROJECT JARMS — TRIAGE SUMMARY")
    print("="*60)
    tx = stt.get("transcript") or "N/A"
    print(f"STT Transcript : {tx[:100]}...")
    print(f"STT Confidence : {stt.get('confidence')}")
    print(f"Urgency Level  : {str(triage.get('urgency')).upper()}")
    print(f"Reasoning      : {triage.get('reasoning')}")
    print(f"Recommended    : {triage.get('recommended_action')}")
    print(f"Flags          : {triage.get('pab_flags')}")
    print("="*60)
