import os
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

models_to_test = ["gemini-1.5-flash", "gemini-2.0-flash"]

for model in models_to_test:
    print(f"Testing {model}...")
    start = time.time()
    try:
        response = client.models.generate_content(
            model=model,
            contents="Say 'Hello' as fast as you can."
        )
        end = time.time()
        print(f"{model} responded in {end - start:.2f} seconds: {response.text.strip()}")
    except Exception as e:
        print(f"Error testing {model}: {e}")
