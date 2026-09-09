import os
import asyncio

from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


def _generate_ai_response(prompt):
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        return response.text

    except Exception as error:
        print(f"AI service error: {type(error).__name__}: {error}")
        return None


async def generate_ai_response(prompt):
    for attempt in range(3):
        print(f"AI request attempt {attempt + 1}/3")

        result = await asyncio.to_thread(
            _generate_ai_response,
            prompt,
)

        if result is not None:
            return result

        if attempt < 2:
            await asyncio.sleep(2)

    return None