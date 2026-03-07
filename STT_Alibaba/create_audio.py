# generate_demo_audios.py
# Project JARMS | Alibaba Cloud / DashScope
# Purpose: Generate 3 demo audios for JARMS:
#   1. Hokkien ah-ma fall emergency
#   2. Malay uncle fire emergency with coughing
#   3. English-speaking child nonsense / false alert

import os
from pathlib import Path

import requests
import dashscope
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
TTS_MODEL = os.getenv("TTS_MODEL", "qwen3-tts-flash")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/api/v1",
)

# You can override these in .env if you want different voices
HOKKIEN_VOICE = os.getenv("HOKKIEN_VOICE", "Roy")
CHINESE_VOICE = os.getenv("CHINESE_VOICE", "Roy")
ENGLISH_VOICE = os.getenv("ENGLISH_VOICE", "Bunny")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "generated_audio")).expanduser().resolve()

# ------------------------------------------------------------------
# SCRIPTS
# ------------------------------------------------------------------
HOKKIEN_SCRIPT = (
    "救命啊…有人無？…我跌倒啊… "
    "我佇便所跋倒去啊…起袂來… "
    "我的尻川骨真痛，腰脊嘛真痛… "
    "我的手嘛痛，頭殼有淡薄暈… "
    "真驚…真艱苦… "
    "阿明啊！你佇佗位？緊來幫我… "
    "救命啊…我站袂起來… "
    "有人來救我無？…緊來啊…"
)

# Chinese uncle, urgent, smoke/fire, coughing
# Keep it short and clear for triage testing.
CHINESE_FIRE_SCRIPT = (
    "救命！救命！屋子里面有火…有很多烟… "
    "咳…咳…我呼吸很困难… "
    "我一个人在家…请快点来帮忙… "
    "厨房那边着火了…烟越来越多…咳…咳… "
    "请马上派人来救我…"
)
# English-speaking child nonsense / accidental / playful
ENGLISH_CHILD_NONSENSE_SCRIPT = (
    "Hello? Um... I pressed the button. "
    "Nothing happened. I was just playing. "
    "My grandpa is sleeping. "
)

SCENARIOS = [
    {
        "name": "hokkien_fall_ahma",
        "voice": HOKKIEN_VOICE,
        "language_type": "Chinese",
        "text": HOKKIEN_SCRIPT,
        "output_file": OUTPUT_DIR / "emergency_hokkien_ahma.mp3",
    },
    {
        "name": "chinese_fire_uncle",
        "voice": CHINESE_VOICE,
        "language_type": "Chinese",
        "text": CHINESE_FIRE_SCRIPT,
        "output_file": OUTPUT_DIR / "emergency_chinese_uncle_fire.mp3",
    },
    {
        "name": "english_child_nonsense",
        "voice": ENGLISH_VOICE,
        "language_type": "English",
        "text": ENGLISH_CHILD_NONSENSE_SCRIPT,
        "output_file": OUTPUT_DIR / "nonsense_english_child.mp3",
    },
]


# ------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------
def _extract_audio_url(response) -> str:
    try:
        return response.output.audio.url
    except Exception:
        pass

    try:
        return response["output"]["audio"]["url"]
    except Exception:
        pass

    try:
        output = getattr(response, "output", None)
        if isinstance(output, dict):
            audio = output.get("audio", {})
            if isinstance(audio, dict) and audio.get("url"):
                return audio["url"]
    except Exception:
        pass

    raise RuntimeError(f"Could not extract audio URL from response: {response}")


def generate_audio(
    *,
    text: str,
    output_path: Path,
    voice: str,
    language_type: str,
) -> bool:
    if not DASHSCOPE_API_KEY:
        print("[tts] ❌ DASHSCOPE_API_KEY is not set.")
        return False

    if not text.strip():
        print("[tts] ❌ Input text is empty.")
        return False

    dashscope.api_key = DASHSCOPE_API_KEY
    dashscope.base_http_api_url = DASHSCOPE_BASE_URL

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        print(
            f"[tts] Sending request | model={TTS_MODEL} | voice={voice} | language={language_type}"
        )

        response = dashscope.MultiModalConversation.call(
            model=TTS_MODEL,
            text=text,
            voice=voice,
            language_type=language_type,
            stream=False,
        )

        status_code = getattr(response, "status_code", None)
        if status_code != 200:
            code = getattr(response, "code", "unknown_code")
            message = getattr(response, "message", "unknown_error")
            print(
                f"[tts] ❌ API error: status={status_code}, code={code}, message={message}"
            )
            return False

        audio_url = _extract_audio_url(response)
        print(f"[tts] Downloading: {audio_url[:100]}...")

        audio_response = requests.get(audio_url, timeout=60)
        audio_response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(audio_response.content)

        print(f"[tts] ✅ Saved: {output_path}")
        return True

    except requests.RequestException as e:
        print(f"[tts] ❌ Download error: {e}")
        return False
    except Exception as e:
        print(f"[tts] ❌ Error: {e}")
        return False


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("🎙️  Project JARMS Demo Audio Generator")
    print("=" * 60)
    print(f"[out] Output directory: {OUTPUT_DIR}\n")

    successes = 0

    for scenario in SCENARIOS:
        print("-" * 60)
        print(f"[scenario] {scenario['name']}")
        print(f"[preview] {scenario['text'][:120]}...")
        ok = generate_audio(
            text=scenario["text"],
            output_path=scenario["output_file"],
            voice=scenario["voice"],
            language_type=scenario["language_type"],
        )
        if ok:
            successes += 1

    print("\n" + "=" * 60)
    print(f"Done. Generated {successes}/{len(SCENARIOS)} audio files.")
    print("Expected outputs:")
    for scenario in SCENARIOS:
        print(f" - {scenario['output_file']}")
