import base64
import json
import os
import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")

# ------------------------
# 1. Load audio
# ------------------------
print(f"[pureadio] Loading audio: {AUDIO_FILE}")
with open(AUDIO_FILE, "rb") as f:
    audio_bytes = f.read()

audio_base64 = base64.b64encode(audio_bytes).decode()
audio_data_uri = f"data:audio/mp3;base64,{audio_base64}"

# ------------------------
# 2. Speech Recognition
# ------------------------
print("[pureadio] Running ASR (qwen3-asr-flash)...")
asr_response = client.chat.completions.create(
    model="qwen3-asr-flash",
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

transcript = asr_response.choices[0].message.content

print("\nRaw Transcript:")
print(transcript)

# ------------------------
# 3. Translation + cleanup
# ------------------------
translation_prompt = f"""
The following is a speech transcript that may contain Hokkien dialect mixed with Mandarin.

Please:
1. Clean up the Chinese transcript
2. Keep the meaning accurate
3. Provide an English translation

Return format:

Chinese (Cleaned):
...

English Translation:
...

Transcript:
{transcript}
"""

print("\n[pureadio] Running translation (qwen-plus)...")
translation_response = client.chat.completions.create(
    model="qwen-plus",
    messages=[
        {"role": "system", "content": "You are a professional translator."},
        {"role": "user", "content": translation_prompt}
    ]
)

translation = translation_response.choices[0].message.content

print("\nTranslated Output:")
print(translation)

# ------------------------
# 4. Save output to file
# ------------------------
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
output_filename = f"transcript_{os.path.splitext(AUDIO_FILE)[0]}_{timestamp}.txt"

output = f"""Audio File : {AUDIO_FILE}
Timestamp  : {timestamp}
{'='*60}

RAW TRANSCRIPT:
{transcript}

{'='*60}

TRANSLATED OUTPUT:
{translation}
"""

with open(output_filename, "w", encoding="utf-8") as f:
    f.write(output)

print(f"\n[pureadio] Output saved to: {output_filename}")