"""
captioner.py — Audio Scene Captioner
======================================
Project JARMS | Alibaba Cloud / DashScope

Purpose:
  Independently infers and describes what is happening in the audio recording
  in plain natural language.

Model: qwen3-omni-flash  (Alibaba multimodal audio model)
"""

import base64
import json
import os
import re

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
AUDIO_FILE = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")

CAPTION_MODEL = "qwen3-omni-flash"
#CAPTION_MODEL = "qwen3-omni-30b-a3b-captioner"


client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# ------------------------------------------------------------------
# SYSTEM PROMPT
# ------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an expert audio scene analyst for Project JARMS — a 24/7 emergency
monitoring service for elderly residents living alone in Singapore HDB rental flats.

Describe in plain English what is happening in the audio, as if you are a paramedic
listening for the first time. Focus on the physical and emotional state of the speaker.

Return ONLY a valid JSON object with the following keys:
caption (string), confidence (float 0.0-1.0), notable_events (list of strings)
"""

# ------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------


def run(audio_path: str) -> dict:
    """Generate audio scene caption using qwen3-omni-flash."""
    print(f"[captioner] Loading audio: {audio_path}")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_b64 = base64.b64encode(audio_bytes).decode()
    audio_data_uri = f"data:audio/mp3;base64,{audio_b64}"

    print(f"[captioner] Sending to model: {CAPTION_MODEL}")
    try:
        response = client.chat.completions.create(
            model=CAPTION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data_uri},
                        },
                        {
                            "type": "text",
                            "text": "Describe the audio scene and return your findings as JSON.",
                        },
                    ],
                },
            ],
            extra_body={"enable_thinking": False},
            temperature=0.3,
        )
        raw_text = response.choices[0].message.content
        print(f"[captioner] Raw output: {raw_text[:200]}...")

        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"caption": raw_text, "confidence": 0.5, "notable_events": []}

    except Exception as e:
        print(f"[captioner] Error: {e}")
        return {
            "caption": f"Analysis failed: {e}",
            "confidence": 0.0,
            "notable_events": [],
        }


# ------------------------------------------------------------------
# STANDALONE
# ------------------------------------------------------------------

if __name__ == "__main__":
    res = run(AUDIO_FILE)
    print(json.dumps(res, indent=2))
