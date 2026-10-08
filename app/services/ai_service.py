import os
import asyncio
from dotenv import load_dotenv
from google import genai
import logging

logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")


def _generate_ai_response(prompt, model):
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        response_text = response.text

        if not response_text:
            logger.error("Gemini returned an empty response")
            return None

        return response_text

    except Exception as error:
        logger.error(
            f"Gemini generation failed: {type(error).__name__}: {error}"
        )
        raise


async def generate_ai_response(prompt):
    for attempt in range(3):
        try:
            result = await asyncio.to_thread(
                _generate_ai_response,
                prompt,
                "gemini-3.6-flash"
            )
            return result

        except Exception as error:
            error_text = str(error)

            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                logger.error(
                    "Gemini 3.6 quota exhausted. Falling back to Gemini 3.5 Flash-Lite."
                )
                try:
                    result = await asyncio.to_thread(
                        _generate_ai_response,
                        prompt,
                        "gemini-3.5-flash-lite",
                    )
                    return result
                except Exception as fallback_error:
                    logger.error(
                        f"Gemini fallback failed: "
                        f"{type(fallback_error).__name__}: {fallback_error}"
                    )
                    return None

            if attempt < 2:
                logger.warning(
                    f"Gemini temporary failure. Retrying... "
                    f"attempt {attempt + 1}/3"
                )
                await asyncio.sleep(2)
                continue

            logger.error(
                "Gemini failed after 3 attempts."
            )
            return None