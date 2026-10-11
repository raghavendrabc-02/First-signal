import asyncio
import logging

from app.tasks import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# httpx logs every request URL at INFO level, and Telegram URLs contain the
# bot token. Only warnings and errors are kept.
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    result = asyncio.run(run_pipeline())

    if result is None:
        raise SystemExit("FirstSignal pipeline failed")
