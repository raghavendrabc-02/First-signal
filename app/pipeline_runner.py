import asyncio
import logging

from app.tasks import run_pipeline

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    result = asyncio.run(run_pipeline())

    if result is None:
        raise SystemExit("FirstSignal pipeline failed")