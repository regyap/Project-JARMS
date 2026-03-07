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
AUDIO_FILE        = os.getenv("AUDIO_FILE", "interviewcoolies.mp3")

CAPTION_MODEL = "qwen3-omni-flash"

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# ------------------------------------------------------------------
# USER CAPTION PROMPT (no system prompt — let the model hear freely)
# ------------------------------------------------------------------
CAPTION_PROMPT = (
    "Listen to this audio and caption what is happening. "
    "Focus on: who is speaking, their emotional and physical state, "
    "any notable sounds (breathing, falls, alarms, background noise), "
    "and the overall urgency of the situation. "
    "Return ONLY a valid JSON object with keys: "
    "caption (string), confidence (float 0.0-1.0), notable_events (list of strings)."
)

# ------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------

def run(audio_path: str) -> dict:
    """Generate audio scene caption using qwen3-omni-flash (no system prompt)."""
    print(f"[captioner] Loading audio: {audio_path}")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_b64      = base64.b64encode(audio_bytes).decode()
    audio_data_uri = f"data:audio/mp3;base64,{audio_b64}"

    print(f"[captioner] Sending to model: {CAPTION_MODEL}")
    try:
        response = client.chat.completions.create(
            model=CAPTION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data_uri}
                        },
                        {"type": "text", "text": CAPTION_PROMPT}
                    ]
                }
            ],
            extra_body={"enable_thinking": False},
            temperature=0.3
        )
        raw_text = response.choices[0].message.content
        print(f"[captioner] Raw output: {raw_text[:200]}...")

        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"caption": raw_text, "confidence": 0.5, "notable_events": []}

    except Exception as e:
        print(f"[captioner] Error: {e}")
        return {
            "caption": f"Analysis failed: {e}",
            "confidence": 0.0,
            "notable_events": []
        }

# ------------------------------------------------------------------
# STANDALONE
# ------------------------------------------------------------------

if __name__ == "__main__":
    res = run(AUDIO_FILE)
    print(json.dumps(res, indent=2))
