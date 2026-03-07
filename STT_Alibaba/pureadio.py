import base64
from openai import OpenAI

client = OpenAI(
    api_key="sk-00edd69755ea4481b1a021ead696d7e7",
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# ------------------------
# 1. Load audio
# ------------------------
with open("interviewcoolies.mp3", "rb") as f:
    audio_bytes = f.read()

audio_base64 = base64.b64encode(audio_bytes).decode()
audio_data_uri = f"data:audio/mp3;base64,{audio_base64}"

# ------------------------
# 2. Speech Recognition
# ------------------------
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

print("Raw Transcript:")
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