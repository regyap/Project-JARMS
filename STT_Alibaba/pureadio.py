"""
pureadio.py — OpenAI Whisper Transcription Pipeline
===================================================

Pipeline:
STEP 1 — Whisper Cloud: Audio → Raw Transcript
STEP 2 — GPT-4o: Phonetic Dialect Correction & Dual Translation
"""

import os
import datetime
import time
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------
# LOAD ENV & VALIDATE
# ---------------------------------------------------

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")

# Fail-fast validation
if not OPENAI_API_KEY:
    raise ValueError("CRITICAL: OPENAI_API_KEY is missing. Please add it to your .env file.")

# Single OpenAI Client for both ASR and LLM tasks
client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------
# STEP 1 — WHISPER ASR
# ---------------------------------------------------

def transcribe_whisper(audio_path):
    print("\n[STEP 1] Whisper Cloud ASR")

    with open(audio_path, "rb") as audio:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio,
            timeout=60
        )

    text = response.text.strip()
    print("Whisper Raw Transcript:")
    print(text[:200])

    return text

# ---------------------------------------------------
# STEP 2 — LINGUISTIC RECONSTRUCTION & TRANSLATION
# ---------------------------------------------------

def refine_and_translate(raw_text):
    print("\n[STEP 2] Dialect Reconstruction & Translation (GPT-4o)")

    SYSTEM = """
    You are an expert linguist analyzing mixed Hokkien, Mandarin, and English speech transcripts from an ASR tool.

    Your Tasks:
    1. Clean: Remove mechanical ASR hallucination loops at the end of the text.
    2. Reconstruct: Correct ASR phonetic mistakes (e.g., hallucinated characters based on dialect sounds). Preserve actual dialect words in their proper characters. Do NOT invent phrases.
    3. Translate: Translate the reconstructed text into highly accurate English. If the speaker used an acronym for a dialect phrase, include the translated meaning in brackets (e.g., "LCT [whole body pain]").

    Provide the final output in EXACTLY this format:

    NATIVE_TRANSCRIPT:
    [Insert the cleaned, phonetically corrected native text here]

    ENGLISH_TRANSLATION:
    [Insert the translated English text here]
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"RAW TRANSCRIPT:\n{raw_text}"}
        ]
    )

    result = response.choices[0].message.content.strip()
    print(result)

    return result

# ---------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------

def run(audio_path):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    start = time.time()

    print("\n==============================")
    print("PUREADIO WHISPER PIPELINE")
    print("==============================")

    # Execute Pipeline
    whisper_text = transcribe_whisper(audio_path)
    final_result = refine_and_translate(whisper_text)

    # Parse Outputs Safely
    native_text = ""
    english_text = ""

    if "NATIVE_TRANSCRIPT:" in final_result and "ENGLISH_TRANSLATION:" in final_result:
        parts = final_result.split("ENGLISH_TRANSLATION:")
        native_text = parts[0].replace("NATIVE_TRANSCRIPT:", "").strip()
        english_text = parts[1].strip()
    else:
        # Fallback just in case the model ignores formatting
        native_text = whisper_text
        english_text = final_result

    # Save to File
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(audio_path))[0]
    output_file = f"transcript_{base}_{timestamp}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("PUREADIO TRANSCRIPTION RESULT\n")
        f.write("="*50 + "\n\n")
        
        f.write("RAW WHISPER ASR\n")
        f.write(whisper_text + "\n\n")
        f.write("="*50 + "\n\n")
        
        f.write("NATIVE\n")
        f.write(native_text + "\n\n")
        
        f.write("ENGLISH\n")
        f.write(english_text + "\n")

    elapsed = time.time() - start

    print("\n==============================")
    print("TRANSCRIPTION COMPLETE")
    print("==============================")
    print(f"Output File : {output_file}")
    print(f"Time Taken  : {elapsed:.2f}s")

    return {
        "raw": whisper_text,
        "native": native_text,
        "english": english_text
    }

# ---------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------

if __name__ == "__main__":
    run(AUDIO_FILE)