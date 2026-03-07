"""
pureadio.py — Whisper + GPT-4o Transcription Pipeline
=======================================================
Project JARMS | OpenAI

Pipeline:
  STEP 1 — Whisper Cloud  : Audio → Raw ASR Transcript
  STEP 2 — GPT-4o         : Phonetic Dialect Correction & Dual Translation

Designed to handle Singaporean elderly callers speaking mixed Hokkien,
Mandarin, and English — including phonetic acronym puns for ailments.

Returns:
  {
    "raw_transcript": str,   # raw Whisper output
    "translation":    str,   # cleaned English translation
    "confidence":     float  # currently fixed at 0.8
  }
"""

import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ------------------------------------------------------------------
# SYSTEM PROMPT  (Whisper → GPT-4o cleanup)
# ------------------------------------------------------------------
REFINE_SYSTEM = """
You are an expert linguist analysing mixed Hokkien, Mandarin, and English speech
transcripts from an ASR tool used in a Singapore elderly care emergency service.

Your Tasks:
1. Clean   — Remove mechanical ASR hallucination loops at the end of the text.
2. Reconstruct — Correct ASR phonetic mistakes (e.g., hallucinated characters
   based on dialect sounds). Preserve actual dialect words in their proper
   characters. Do NOT invent phrases.
3. Translate — Translate the reconstructed text into highly accurate English.
   If the speaker used an acronym for a dialect phrase, include the translated
   meaning in brackets (e.g., "LCT [whole body pain]").

Provide the final output in EXACTLY this format:

NATIVE_TRANSCRIPT:
[Insert the cleaned, phonetically corrected native text here]

ENGLISH_TRANSLATION:
[Insert the translated English text here]
"""


# ------------------------------------------------------------------
# STEP 1 — WHISPER ASR
# ------------------------------------------------------------------

def _transcribe_whisper(audio_path: str, client: OpenAI) -> str:
    print("[pureadio] STEP 1 — Whisper Cloud ASR")
    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            timeout=120,
        )
    text = response.text.strip()
    print(f"[pureadio] Whisper raw output ({len(text)} chars): {text[:120]}...")
    return text


# ------------------------------------------------------------------
# STEP 2 — DIALECT RECONSTRUCTION & TRANSLATION
# ------------------------------------------------------------------

def _refine_and_translate(raw_text: str, client: OpenAI) -> str:
    print("[pureadio] STEP 2 — Dialect Reconstruction & Translation (GPT-4o)")
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.1,
        messages=[
            {"role": "system", "content": REFINE_SYSTEM},
            {"role": "user", "content": f"RAW TRANSCRIPT:\n{raw_text}"},
        ],
    )
    result = response.choices[0].message.content.strip()
    print(f"[pureadio] GPT-4o output: {result[:200]}...")
    return result


# ------------------------------------------------------------------
# MAIN PUBLIC FUNCTION
# ------------------------------------------------------------------

def run(audio_path: str) -> dict:
    """
    Transcribe audio and return structured result for run_triage.py.

    Args:
        audio_path: absolute path to the (temp) audio file

    Returns:
        {
            "raw_transcript": str,
            "translation":    str,
            "confidence":     float,
        }
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"[pureadio] Audio file not found: {audio_path}")

    if not OPENAI_API_KEY:
        raise ValueError("[pureadio] OPENAI_API_KEY is missing — add it to your .env")

    client = OpenAI(api_key=OPENAI_API_KEY)

    start = time.time()
    print("\n==============================")
    print("PUREADIO WHISPER PIPELINE")
    print("==============================")

    # Execute pipeline
    whisper_text = _transcribe_whisper(audio_path, client)
    final_result = _refine_and_translate(whisper_text, client)

    # Parse outputs safely
    native_text = ""
    english_text = ""

    if "NATIVE_TRANSCRIPT:" in final_result and "ENGLISH_TRANSLATION:" in final_result:
        parts = final_result.split("ENGLISH_TRANSLATION:")
        native_text = parts[0].replace("NATIVE_TRANSCRIPT:", "").strip()
        english_text = parts[1].strip()
    else:
        # Fallback: model ignored format
        native_text = whisper_text
        english_text = final_result

    elapsed = time.time() - start
    print(f"[pureadio] Done in {elapsed:.2f}s")

    return {
        "raw_transcript": native_text or whisper_text,
        "translation": english_text,
        "confidence": 0.8,
    }


# ------------------------------------------------------------------
# STANDALONE ENTRY POINT
# ------------------------------------------------------------------

if __name__ == "__main__":
    import os
    audio_file = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")
    result = run(audio_file)
    print("\n==============================")
    print("PUREADIO RESULT")
    print("==============================")
    print(f"Raw Transcript : {result['raw_transcript'][:200]}")
    print(f"Translation    : {result['translation'][:200]}")
    print(f"Confidence     : {result['confidence']}")
