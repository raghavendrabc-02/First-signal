import asyncio

from app.celery_app import celery_app
from app.collectors.rss import collect_rss
from app.collectors.rss_sources import RSS_SOURCES
from app.database.connection import SessionLocal
from app.models.article import Article
from app.ranking.ranker import select_best_article
from app.research.research_engine import generate_research_brief
from app.services.script_service import generate_script
from app.services.telegram_service import send_telegram_message



async def run_pipeline():
    for rss_source in RSS_SOURCES:
        await collect_rss(**rss_source)

    db = SessionLocal()

    try:
        articles = db.query(Article).all()

        best_article = select_best_article(articles)

        if best_article is None:
            print("No suitable article found")
            return None

        print(f"Best article selected: {best_article.title}")

        research_result = await generate_research_brief(best_article)

        if research_result is None:
            print("Could not generate research brief")
            return None

        script = await generate_script(
            best_article,
            research_result["research"],
        )

        if script is None:
            print("Could not generate script")
            return None

        message = f"""
        🚨 FirstSignal Daily Story

        📰 {best_article.title}

        🎬 Script:

        {script}
        """

        await send_telegram_message(message)

        print("Telegram message sent successfully")
        print("Daily pipeline completed successfully")

        return {
            "article_id": best_article.id,
            "title": best_article.title,
            "script": script,
        }

    finally:
        db.close()


@celery_app.task
def run_daily_pipeline():
    return asyncio.run(run_pipeline())