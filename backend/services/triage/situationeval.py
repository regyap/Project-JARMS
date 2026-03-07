"""
situationeval.py — Paralinguistic Signal Detector
===================================================
Project JARMS | Alibaba Cloud / DashScope

Purpose:
  Listens to the raw audio and detects clinically relevant signals that
  a plain transcript cannot capture:
    • Impairment signals  — laboured breathing, weak voice, choppy speech
    • High-risk triggers  — pain vocalisations, crying, screaming, breath loss
    • Environmental cues  — alarms, falls, banging

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

EVAL_MODEL = "qwen3-omni-flash"

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# ------------------------------------------------------------------
# SYSTEM PROMPT
# ------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a clinical audio analyst for Project JARMS — a 24/7 emergency monitoring
service for elderly residents living alone in Singapore HDB rental flats.

Your task is to listen carefully to the raw audio recording and identify
NON-VERBAL and PARALINGUISTIC signals that may indicate medical distress,
cognitive impairment, or environmental danger. You are NOT transcribing speech.
You are detecting signs.

HIGH RISK TRIGGERS to detect:
pain_vocalization, screaming, crying, gasping, choking, gurgling,
loss_of_breath, rapid_shallow_breathing, breath_cessation

IMPAIRMENT SIGNALS to detect:
laboured_breathing, wheezing, weak_faint_voice, slurred_speech,
choppy_fragmented_speech, long_silent_pauses, confusion_repetition,
slow_response, incoherent_mumbling, trembling_voice

ENVIRONMENTAL CUES to detect:
background_alarm, fall_sound, banging_noise, phone_ringing,
silence_after_trigger, tv_radio_background, door_sound

SEVERITY SCALE:
critical — immediate life threat (gasping, breath_cessation, screaming)
high     — strong distress signals (laboured breathing, loss of breath, pain)
medium   — moderate concern (weak voice, choppy speech, long pauses)
low      — minimal/no concerning signals detected

Return ONLY a valid JSON object with the following keys:
impairment_signals, high_risk_triggers, environmental_cues,
severity (low|medium|high|critical), reasoning
"""

# ------------------------------------------------------------------
# CORE FUNCTION
# ------------------------------------------------------------------

def run(audio_path: str) -> dict:
    """Analyse audio paralinguistic signals using qwen3-omni-flash."""
    print(f"[situationeval] Loading audio: {audio_path}")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_b64     = base64.b64encode(audio_bytes).decode()
    audio_data_uri = f"data:audio/mp3;base64,{audio_b64}"

    print(f"[situationeval] Sending to model: {EVAL_MODEL}")
    try:
        response = client.chat.completions.create(
            model=EVAL_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data_uri}
                        },
                        {"type": "text", "text": "Analyse the audio and return your findings as JSON."}
                    ]
                }
            ],
            extra_body={"enable_thinking": False},
            temperature=0.1
        )
        raw_text = response.choices[0].message.content
        print(f"[situationeval] Raw output: {raw_text[:200]}...")

        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "No JSON found", "raw_output": raw_text}

    except Exception as e:
        print(f"[situationeval] Error: {e}")
        return {
            "impairment_signals": [],
            "high_risk_triggers": [],
            "environmental_cues": [],
            "severity": "medium",
            "reasoning": f"Analysis failed: {e}"
        }

# ------------------------------------------------------------------
# STANDALONE
# ------------------------------------------------------------------

if __name__ == "__main__":
    res = run(AUDIO_FILE)
    print(json.dumps(res, indent=2))
