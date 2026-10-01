import asyncio

from app.tasks import run_pipeline


if __name__ == "__main__":
    asyncio.run(run_pipeline())