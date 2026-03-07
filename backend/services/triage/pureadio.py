"""
pureadio.py — Native Multimodal Audio Translation (File API Method)
================================================
Project JARMS | Google Gemini API

Purpose:
  Processes a raw audio file directly using Gemini 2.5 Flash via the File API.
  This avoids massive inline Base64 payloads (which cause network hangs)
  and completely removes the need for local FFmpeg installation.
"""

import os
import datetime
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")

# Using Flash for speed and free-tier access
MODEL_NAME = "gemini-2.5-flash"

client = genai.Client(api_key=GEMINI_API_KEY)

# ------------------------------------------------------------------
# GLOSSARY FOR REFINEMENT
# ------------------------------------------------------------------
HOKKIEN_GLOSSARY = """
HOKKIEN / MINNAN GLOSSARY (Phonetic Sounds -> Correct Characters):
- "LCT" -> 拢总痛 (Everything hurts / Whole body aches)
- "DPT" -> 淡薄痛 (Hurts a little bit)
- "PTL" -> 破头颅 (Splitting headache)
- "Lau jio" / "Liao jio" -> 救命 (Help)
- "Tiam" / "Thiam" -> 痛 (Pain / Sore / Hurt)
- "Doh" / "Deh" -> 在哪里 (Where)
- "Boe" -> 不能 / 还没有 (Cannot / Not yet)
- "Tao ka" -> 头痛 (Headache)
- "Ka chiak" -> 背部 (Back)
- "Gua" -> 我 (I)
- "Le" -> 你 (You)
- "Lim" -> 喝 (Drink)
- "Jia" -> 吃 (Eat)
"""

# ------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------


def run(audio_path: str) -> dict:
    print(f"[pureadio] Uploading audio securely via File API: {audio_path}")

    # 1. Upload the file cleanly (avoids the Base64 payload hang)
    try:
        uploaded_audio = client.files.upload(file=audio_path)
        print(f"[pureadio] Upload successful. File URI: {uploaded_audio.uri}")
    except Exception as e:
        print(f"[pureadio] Failed to upload file to Gemini: {e}")
        return {}

    # 2. Call the Gemini API
    print(f"[pureadio] Processing audio with {MODEL_NAME}...")

    prompt = f"""
You are an expert in Singaporean Chinese dialects (Hokkien, Minnan, Teochew) and medical triage.
Listen to the audio. The speaker uses heavily accented dialect mixed with English acronyms (which might be phonetic puns for ailments).

GLOSSARY TO HELP YOU DECODE:
{HOKKIEN_GLOSSARY}

TASK:
Translate the audio directly into clear, high-precision English, capturing the medical urgency or the specific ailments described. 
Do NOT output the raw or cleaned Chinese transcript. Output ONLY the English translation.
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[uploaded_audio, prompt],
            config={"temperature": 0.1},
        )
        translation_output = response.text
        print(f"[pureadio] Translation Complete!\n")
    except Exception as e:
        print(f"[pureadio] API generation failed: {e}")
        return {}
    finally:
        # 3. Clean up: Delete the file from Google's servers immediately
        try:
            client.files.delete(name=uploaded_audio.name)
            print("[pureadio] Cloud file cleaned up.")
        except Exception:
            pass

    # 4. Save output to file
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_filename = f"transcript_{base_name}_{timestamp}.txt"

    file_content = f"""Audio File : {audio_path}
Timestamp  : {timestamp}
{'='*60}

REFINED ENGLISH TRANSLATION:
{translation_output}
"""

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(file_content)

    print(f"[pureadio] Output saved to: {output_filename}")

    return {"translation": translation_output, "output_filename": output_filename}


# ------------------------------------------------------------------
# STANDALONE ENTRY POINT
# ------------------------------------------------------------------

if __name__ == "__main__":
    result = run(AUDIO_FILE)
    if result:
        print("\n" + "=" * 60)
        print("  PUREADIO RESULT")
        print("=" * 60)
        print(f"  Output file  : {result['output_filename']}")
        print(f"  Translation:\n  {result['translation'][:300]}...")
        print("=" * 60)
