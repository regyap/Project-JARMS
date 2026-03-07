import base64
import json
import os
import re
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# CONFIG
# -----------------------------

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "YOUR_DASHSCOPE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")

AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")
USER_ID = int(os.getenv("USER_ID", "1"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

STT_MODEL = "qwen3-asr-flash"           # Dedicated Alibaba ASR model (handles longer audio)
TRIAGE_MODEL = "qwen3-235b-a22b"      # Alibaba Qwen3 MoE model for triage reasoning
TRIAGE_PROTOCOL_FILE = "triage_protocol.md"


# -----------------------------
# CLIENTS
# -----------------------------

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# Supabase client is created lazily inside save_to_supabase() so a
# placeholder URL does not crash the script at startup.


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
# STEP 0: Load Triage Protocol
# -----------------------------

def load_triage_protocol(filepath: str = TRIAGE_PROTOCOL_FILE) -> str:
    """Load the triage protocol document to ground the LLM."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# -----------------------------
# STEP 1: Get User Language
# -----------------------------

def get_user_language(user_id: int) -> str:
    """Fetch preferred language from Supabase users table."""
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        data = (
            sb.table("users")
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
# STEP 2: Speech-to-Text (STT)
# -----------------------------

def run_stt(audio_path: str, language: str) -> dict:
    """
    Transcribe audio using Alibaba Qwen ASR via OpenAI-compatible API.
    Step 1: qwen3-asr-flash for raw transcription (no system prompt - ASR-only model).
    Step 2: qwen-plus to assess confidence, translate, and format as JSON.
    Returns: { transcript, confidence, raw_output }
    """
    print(f"\n[STT] Loading audio from: {audio_path}")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_base64 = base64.b64encode(audio_bytes).decode()
    audio_data_uri = f"data:audio/mp3;base64,{audio_base64}"

    # --- Step 1: Raw transcription via ASR model (no system prompt) ---
    print(f"[STT] Sending to ASR model: {STT_MODEL}")
    asr_response = client.chat.completions.create(
        model=STT_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_data_uri
                        }
                    }
                ]
            }
        ]
    )

    raw_transcript = asr_response.choices[0].message.content
    print(f"[STT] Raw transcript: {raw_transcript[:200]}...")

    # --- Step 2: Confidence + cleanup via qwen-plus ---
    cleanup_prompt = f"""You are a medical transcript quality assessor for a PAB (Personal Alert Button) emergency system.

Given this raw audio transcript, return a JSON object with:
- "transcript": Clean the transcript. Translate it into {language}. If the audio was silence or too poor to understand, write "SILENCE_DETECTED".
- "confidence": A float 0.0-1.0 for how clear the audio was (1.0=perfectly clear, 0.7=mostly clear, 0.3=difficult, 0.1=nearly inaudible).
- "language_detected": The language spoken in the original audio.

Return ONLY valid JSON, no markdown fences.

Raw transcript:
{raw_transcript}"""

    cleanup_response = client.chat.completions.create(
        model=TRIAGE_MODEL,
        messages=[
            {"role": "system", "content": "You are a medical transcript quality assessor. Return only valid JSON."},
            {"role": "user", "content": cleanup_prompt}
        ],
        temperature=0.1
    )

    raw_output = cleanup_response.choices[0].message.content
    print(f"[STT] Cleanup output: {raw_output[:200]}...")

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_output).strip()

    try:
        result = json.loads(cleaned)
        transcript = result.get("transcript", raw_transcript)
        confidence = float(result.get("confidence", 0.7))
        language_detected = result.get("language_detected", "unknown")
    except (json.JSONDecodeError, ValueError):
        print("[WARN] Could not parse STT cleanup JSON. Using raw transcript.")
        transcript = raw_transcript
        confidence = 0.7
        language_detected = "unknown"

    # Check for silence
    silence_detected = (
        "SILENCE_DETECTED" in transcript or
        "AUDIO_TOO_POOR" in transcript or
        confidence < 0.2
    )

    print(f"[STT] Transcript ({confidence:.2f} confidence): {transcript[:100]}...")
    print(f"[STT] Language detected: {language_detected}")
    print(f"[STT] Silence detected: {silence_detected}")

    return {
        "transcript": transcript,
        "confidence": confidence,
        "language_detected": language_detected,
        "silence_detected": silence_detected,
        "raw_output": raw_output
    }


# -----------------------------
# STEP 3: LLM Triage
# -----------------------------

def run_triage(transcript: str, stt_confidence: float, protocol: str) -> dict:
    """
    Run triage analysis using Alibaba Qwen LLM grounded by the triage protocol.
    Returns structured triage result JSON.
    """
    silence_note = ""
    if "SILENCE_DETECTED" in transcript or stt_confidence < 0.2:
        silence_note = "\n[SYSTEM NOTE: Audio contained silence or was too poor to transcribe. Set silence_after_trigger=true and low_confidence_ai=true in your flags.]"

    triage_system_prompt = f"""You are an AI triage assistant for Project JARMS — a 24/7 emergency monitoring service for elderly residents living alone in HDB rental flats in Singapore.

You receive audio transcripts from Personal Alert Buttons (PABs) triggered by elderly residents.
Your job is to analyse the transcript and determine the urgency level using the triage protocol below.

=== TRIAGE PROTOCOL ===
{protocol}
=== END PROTOCOL ===

CRITICAL RULES:
1. Always follow the classification rules in order (life_threatening first, then emergency, etc.)
2. When in doubt, ESCALATE — never downgrade when uncertain
3. If transcript is empty, silent, or confidence is low, set silence_after_trigger=true and low_confidence_ai=true
4. Hard override rules ALWAYS apply — no exceptions
5. You MUST return ONLY a valid JSON object. No markdown, no explanation outside the JSON.
6. Recommended actions must ONLY be from the allowed actions list in the protocol

The human operator will act on your recommendation. Be precise and conservative (err toward higher urgency).
"""

    triage_user_prompt = f"""Analyse this PAB audio transcript and apply the triage protocol:

TRANSCRIPT:
{transcript}

STT CONFIDENCE SCORE: {stt_confidence:.2f}{silence_note}

Return the triage result as a JSON object matching the Required Output Schema in the protocol exactly."""

    print(f"\n[TRIAGE] Sending transcript to triage model: {TRIAGE_MODEL}")
    response = client.chat.completions.create(
        model=TRIAGE_MODEL,
        messages=[
            {"role": "system", "content": triage_system_prompt},
            {"role": "user", "content": triage_user_prompt}
        ],
        temperature=0.1   # Low temperature for consistent, deterministic triage
    )

    raw_output = response.choices[0].message.content
    print(f"[TRIAGE] Raw output: {raw_output[:300]}...")

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw_output).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print("[WARN] Could not parse triage JSON. Returning safe fallback.")
        result = {
            "urgency_bucket": "requires_review",
            "urgency_score": 0.5,
            "triage_flags": {
                "low_confidence_ai": True,
                "conflicting_ai_outputs": True
            },
            "reasoning": "Triage model output could not be parsed. Defaulting to requires_review for human operator review.",
            "recommended_actions": ["call_patient_now"],
            "sbar": {
                "situation": "Unable to parse triage output.",
                "background": "STT transcript was provided but triage model returned unparseable output.",
                "assessment": "Uncertain. Requires human review.",
                "recommendation": "Call patient immediately and assess manually."
            }
        }

    return result


# -----------------------------
# STEP 4: Save to Supabase
# -----------------------------

def save_to_supabase(user_id: int, stt_result: dict, triage_result: dict, audio_file: str) -> dict:
    """
    Save the full pipeline result to the Supabase triages table.
    Returns the inserted row data.
    """
    flags = triage_result.get("triage_flags", {})
    sbar = triage_result.get("sbar", {})

    record = {
        "user_id": user_id,
        "audio_file": audio_file,
        "transcript": stt_result.get("transcript"),
        "stt_confidence": stt_result.get("confidence"),
        "language_detected": stt_result.get("language_detected"),
        "silence_detected": stt_result.get("silence_detected", False),
        "urgency_bucket": triage_result.get("urgency_bucket"),
        "urgency_score": triage_result.get("urgency_score"),
        "triage_flags": json.dumps(flags),
        "reasoning": triage_result.get("reasoning"),
        "recommended_actions": json.dumps(triage_result.get("recommended_actions", [])),
        "sbar_situation": sbar.get("situation"),
        "sbar_background": sbar.get("background"),
        "sbar_assessment": sbar.get("assessment"),
        "sbar_recommendation": sbar.get("recommendation"),
    }

    if DRY_RUN:
        print("\n[DB] DRY_RUN=true — skipping Supabase insert. Record that would be saved:")
        print(json.dumps({k: str(v)[:80] for k, v in record.items()}, indent=2))
        return {}

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Supabase: {e}")
        return {}

    try:
        response = supabase.table("triages").insert(record).execute()
        print(f"\n[DB] Saved to Supabase. Row ID: {response.data[0].get('id', 'N/A')}")
        return response.data[0]
    except Exception as e:
        print(f"\n[ERROR] Could not save to Supabase: {e}")
        return {}


# -----------------------------
# STEP 5: Print Summary
# -----------------------------

def print_summary(stt_result: dict, triage_result: dict):
    """Print a clean operator-facing summary to the console."""
    bucket = triage_result.get("urgency_bucket", "unknown").upper()
    score = triage_result.get("urgency_score", 0.0)
    actions = triage_result.get("recommended_actions", [])
    sbar = triage_result.get("sbar", {})

    bucket_colors = {
        "LIFE_THREATENING": "🔴",
        "EMERGENCY": "🟠",
        "UNKNOWN": "⚫",
        "REQUIRES_REVIEW": "🟡",
        "MINOR_EMERGENCY": "🟡",
        "NON_EMERGENCY": "🟢"
    }
    icon = bucket_colors.get(bucket, "⚪")

    print("\n" + "="*60)
    print("  PROJECT JARMS — TRIAGE RESULT")
    print("="*60)
    print(f"  {icon}  URGENCY BUCKET : {bucket}")
    print(f"  📊  URGENCY SCORE  : {score:.2f}")
    print(f"  🎤  STT CONFIDENCE : {stt_result.get('confidence', 0):.2f}")
    print(f"  🌐  LANGUAGE       : {stt_result.get('language_detected', 'unknown')}")
    print(f"  🔇  SILENCE        : {stt_result.get('silence_detected', False)}")
    print("-"*60)
    print("  📝  TRANSCRIPT:")
    print(f"  {stt_result.get('transcript', '')[:200]}")
    print("-"*60)
    print("  💡  REASONING:")
    print(f"  {triage_result.get('reasoning', '')[:300]}")
    print("-"*60)
    print("  📋  SBAR:")
    print(f"  S: {sbar.get('situation', '')}")
    print(f"  B: {sbar.get('background', '')}")
    print(f"  A: {sbar.get('assessment', '')}")
    print(f"  R: {sbar.get('recommendation', '')}")
    print("-"*60)
    print("  ✅  RECOMMENDED ACTIONS:")
    for action in actions:
        print(f"     → {action}")

    # Print active flags
    flags = triage_result.get("triage_flags", {})
    active_flags = [k for k, v in flags.items() if v]
    if active_flags:
        print("-"*60)
        print("  🚩  ACTIVE FLAGS:")
        for flag in active_flags:
            print(f"     • {flag}")
    print("="*60)


# -----------------------------
# MAIN
# -----------------------------

def main():
    print("\n🚀 Project JARMS — STT + Triage Pipeline Starting")
    print(f"   Audio file : {AUDIO_FILE}")
    print(f"   User ID    : {USER_ID}")

    # Step 0: Load triage protocol
    print("\n[INIT] Loading triage protocol...")
    triage_protocol = load_triage_protocol()
    print(f"[INIT] Protocol loaded ({len(triage_protocol)} chars)")

    # Step 1: Get user language
    language = get_user_language(USER_ID)
    print(f"[INIT] User preferred language: {language}")

    # Step 2: Run STT
    stt_result = run_stt(AUDIO_FILE, language)

    # Step 3: Run triage
    triage_result = run_triage(
        transcript=stt_result["transcript"],
        stt_confidence=stt_result["confidence"],
        protocol=triage_protocol
    )

    # Step 4: Print summary
    print_summary(stt_result, triage_result)

    # Step 5: Save to Supabase
    save_to_supabase(USER_ID, stt_result, triage_result, AUDIO_FILE)

    print("\n✅ Pipeline complete.")


if __name__ == "__main__":
    main()
