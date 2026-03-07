import os, sys
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

sys.stdout.reconfigure(encoding='utf-8')
for m in client.models.list():
    print(m.name)
