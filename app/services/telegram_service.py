import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Telegram credentials are not configured")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    # httpx error messages include the request URL, which contains the bot
    # token, so only the error type is surfaced.
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
    except httpx.HTTPError as error:
        raise RuntimeError(
            f"Telegram request failed: {type(error).__name__}"
        ) from None

    try:
        data = response.json()
    except ValueError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    if response.status_code != 200 or data.get("ok") is not True:
        description = data.get("description", "no description returned")
        raise RuntimeError(
            f"Telegram sendMessage failed: HTTP {response.status_code}: {description}"
        )

    return data
