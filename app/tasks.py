import asyncio
import logging

from app.celery_app import celery_app
from app.collectors.rss import collect_rss
from app.collectors.rss_sources import RSS_SOURCES
from app.database.connection import SessionLocal
from app.models.article import Article
from app.ranking.ranker import rank_articles
from app.research.research_engine import generate_research_brief
from app.services.script_service import generate_script
from app.services.telegram_service import send_telegram_message


logger = logging.getLogger(__name__)


async def run_pipeline():
    for rss_source in RSS_SOURCES:
        await collect_rss(**rss_source)

    db = SessionLocal()

    try:
        articles = db.query(Article).all()

        ranked_articles = rank_articles(articles)

        if not ranked_articles:
            logger.warning("No suitable article found")
            return None

        for article in ranked_articles:
            logger.info(f"Trying article: {article.title}")

            research_result = await generate_research_brief(article)

            if research_result is None:
                logger.warning(
                    f"Could not research article: {article.title}"
                )
                continue

            script = await generate_script(
                article,
                research_result["research"],
            )

            if script is None:
                logger.warning(
                    f"Could not generate script: {article.title}"
                )
                continue

            logger.info(
                f"Article successfully processed: {article.title}"
            )
            break

        else:
            logger.error("Could not process any ranked article")
            return None

        message = f"""
🚨 FirstSignal Daily Story

📰 {article.title}

🎬 Script:

{script}
"""

        await send_telegram_message(message)

        logger.info("Telegram message sent successfully")
        logger.info("Daily pipeline completed successfully")

        return {
            "article_id": article.id,
            "title": article.title,
            "script": script,
        }

    finally:
        db.close()


@celery_app.task
def run_daily_pipeline():
    return asyncio.run(run_pipeline())