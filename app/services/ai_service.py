import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
import httpx
import logging

logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

PRIMARY_MODEL = "gemini-3.6-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

# No tools are passed, so automatic function calling is never used.
# Disabling it removes the misleading AFC warning from the logs.
GENERATION_CONFIG = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


def _generate_ai_response(prompt, model=PRIMARY_MODEL):
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=GENERATION_CONFIG,
        )

        response_text = response.text

        if not response_text:
            logger.error(f"Gemini ({model}) returned an empty response")
            return None

        return response_text

    except Exception as error:
        logger.error(
            f"Gemini ({model}) generation failed: {type(error).__name__}: {error}"
        )
        raise


def _is_quota_error(error):
    return isinstance(error, errors.ClientError) and error.code == 429


def _is_transient_error(error):
    return isinstance(error, (errors.ServerError, httpx.TransportError))


async def _try_fallback_model(prompt):
    logger.warning(f"Falling back to {FALLBACK_MODEL}")

    try:
        return await asyncio.to_thread(
            _generate_ai_response,
            prompt,
            FALLBACK_MODEL,
        )
    except Exception as fallback_error:
        logger.error(
            f"Gemini fallback failed: "
            f"{type(fallback_error).__name__}: {fallback_error}"
        )
        return None


async def generate_ai_response(prompt):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await asyncio.to_thread(
                _generate_ai_response,
                prompt,
                PRIMARY_MODEL,
            )

        except Exception as error:
            if _is_quota_error(error):
                logger.error(f"{PRIMARY_MODEL} quota exhausted")
                return await _try_fallback_model(prompt)

            if not _is_transient_error(error):
                logger.error(
                    "Gemini error is not retryable; not retrying to save quota"
                )
                return None

            if attempt < MAX_ATTEMPTS:
                delay = RETRY_DELAY_SECONDS * attempt
                logger.warning(
                    f"Gemini temporary failure. Retrying in {delay}s... "
                    f"attempt {attempt}/{MAX_ATTEMPTS}"
                )
                await asyncio.sleep(delay)
                continue

            logger.error(
                f"{PRIMARY_MODEL} failed after {MAX_ATTEMPTS} attempts"
            )
            return await _try_fallback_model(prompt)
