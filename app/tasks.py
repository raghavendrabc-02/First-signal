import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.collectors.rss import collect_rss
from app.collectors.rss_sources import RSS_SOURCES
from app.database.connection import SessionLocal
from app.filters.topic_dedup import find_covered_story
from app.models.article import Article
from app.ranking.ranker import rank_articles
from app.research.research_engine import generate_research_brief
from app.services.script_service import generate_script
from app.services.telegram_service import send_telegram_message


logger = logging.getLogger(__name__)

# Fetching an article page costs no Gemini quota, so a few candidates can be
# tried when a publisher blocks the request (e.g. 403). Gemini failures stop
# the pipeline instead of moving on to the next article.
MAX_ARTICLE_CANDIDATES = 3

# Only articles published within this window are considered for selection.
MAX_ARTICLE_AGE_DAYS = 7

# Candidates are compared against stories delivered within this window. Older
# deliveries no longer block a new development on the same subject.
COVERED_STORY_WINDOW_DAYS = 30


def _utc_now():
    # published_at and delivered_at are stored as naive UTC timestamps.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_eligible_articles(db, now):
    covered_articles = db.scalars(
        select(Article).where(
            Article.delivered_at.is_not(None),
            Article.delivered_at >= now - timedelta(days=COVERED_STORY_WINDOW_DAYS),
        )
    ).all()

    recent_articles = db.scalars(
        select(Article).where(
            Article.delivered_at.is_(None),
            Article.published_at >= now - timedelta(days=MAX_ARTICLE_AGE_DAYS),
        )
    ).all()

    eligible_articles = []

    for article in recent_articles:
        covered_article = find_covered_story(article, covered_articles)

        if covered_article is not None:
            logger.info(
                f"Skipping already covered story: {article.title} "
                f"(delivered as: {covered_article.title})"
            )
            continue

        eligible_articles.append(article)

    logger.info(
        f"{len(eligible_articles)} eligible of {len(recent_articles)} articles "
        f"from the last {MAX_ARTICLE_AGE_DAYS} days "
        f"({len(covered_articles)} stories delivered in the last "
        f"{COVERED_STORY_WINDOW_DAYS} days)"
    )

    return eligible_articles


def load_ranked_articles(now):
    # The session is closed before any webpage or Gemini call, so no database
    # transaction stays open during slow network work. The returned articles
    # are detached but keep their loaded column values.
    db = SessionLocal()

    try:
        return rank_articles(get_eligible_articles(db, now))
    finally:
        db.close()


def record_delivery(article_id, delivered_at, telegram_message_id):
    db = SessionLocal()

    try:
        result = db.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(
                delivered_at=delivered_at,
                telegram_message_id=telegram_message_id,
            )
        )
        db.commit()
    finally:
        db.close()

    if result.rowcount != 1:
        logger.warning(
            f"Delivery recording updated {result.rowcount} rows "
            f"for article_id={article_id}"
        )


def _telegram_message_id(telegram_response):
    result = telegram_response.get("result")

    if isinstance(result, dict) and isinstance(result.get("message_id"), int):
        return result["message_id"]

    return None


async def run_pipeline():
    logger.info("Stage 1/5: Collecting RSS feeds")

    for rss_source in RSS_SOURCES:
        await collect_rss(**rss_source)

    logger.info("Stage 2/5: Ranking articles")

    now = _utc_now()

    ranked_articles = load_ranked_articles(now)

    logger.info(f"Ranked {len(ranked_articles)} articles")

    if not ranked_articles:
        logger.error(
            "Stage 2/5 failed: No fresh article that has not already "
            "been covered"
        )
        return None

    logger.info("Stage 3/5: Researching article")

    article = None
    research_result = None

    for candidate in ranked_articles[:MAX_ARTICLE_CANDIDATES]:
        logger.info(f"Selected article: {candidate.title}")

        research_result = await generate_research_brief(candidate)

        if research_result is not None:
            article = candidate
            break

        logger.warning(
            f"Could not fetch article, trying next ranked article: "
            f"{candidate.title}"
        )

    if article is None:
        logger.error(
            f"Stage 3/5 failed: Could not fetch any of the top "
            f"{MAX_ARTICLE_CANDIDATES} ranked articles"
        )
        return None

    if research_result["research"] is None:
        logger.error(
            f"Stage 3/5 failed: Gemini research failed for: {article.title}"
        )
        return None

    logger.info("Stage 4/5: Generating script")

    script = await generate_script(
        article,
        research_result["research"],
    )

    if script is None:
        logger.error(
            f"Stage 4/5 failed: Could not generate script: {article.title}"
        )
        return None

    logger.info(
        f"Article successfully processed: {article.title}"
    )

    message = f"""
🚨 FirstSignal Daily Story

📰 {article.title}

🎬 Script:

{script}
"""

    logger.info("Stage 5/5: Sending Telegram message")

    telegram_response = await send_telegram_message(message)

    message_id = _telegram_message_id(telegram_response)

    if message_id is None:
        logger.warning(
            "Telegram confirmed delivery but returned no message_id"
        )

    logger.info(
        f"Telegram message sent successfully (message_id={message_id})"
    )

    try:
        record_delivery(article.id, _utc_now(), message_id)
    except Exception:
        logger.exception(
            f"Telegram message was sent but delivery could not be "
            f"recorded; this story may be selected again: {article.title}"
        )
        raise

    logger.info("Daily pipeline completed successfully")

    return {
        "article_id": article.id,
        "title": article.title,
        "script": script,
    }
