import asyncio
import logging

import feedparser
import httpx
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from sqlalchemy import select

from app.collectors.rss_sources import RSS_SOURCES
from app.database.connection import SessionLocal
from app.models.article import Article

logger = logging.getLogger(__name__)


async def collect_rss(url, source, niche):
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
    except httpx.HTTPError as error:
        logger.error(f"{source} - {niche}: Could not fetch feed: {error}")
        return

    try:
        feed = feedparser.parse(response.content)
    except Exception as error:
        logger.error(f"{source} - {niche}: Could not parse feed: {error}")
        return

    if feed.bozo:
        logger.error(f"{source} - {niche}: Could not parse feed")
        return

    if not feed.entries:
        logger.warning(f"{source} - {niche}: No usable entries in feed")
        return

    db = SessionLocal()

    saved = 0
    skipped = 0
    seen_urls = set()


    try:
        for article_data in feed.entries:
            title = article_data.get("title")
            article_url = article_data.get("link")
            published = article_data.get("published")

            if not isinstance(title, str) or not title.strip():
                logger.warning(f"{source} - {niche}: Skipping article with missing title")
                skipped += 1
                continue

            if not isinstance(article_url, str) or not article_url.strip():
                logger.warning(f"{source} - {niche}: Skipping article with missing link")
                skipped += 1
                continue

            title = title.strip()
            article_url = article_url.strip()

            if not isinstance(published, str) or not published.strip():
                logger.warning(f"{source} - {niche}: Skipping article with missing published date")
                skipped += 1
                continue

            try:
                published_at = parsedate_to_datetime(published)
            except (TypeError, ValueError):
                logger.warning(f"{source} - {niche}: Skipping article with invalid published date")
                skipped += 1
                continue

            existing = db.scalar(
                select(Article).where(Article.url == article_url)
            )

            if existing or article_url in seen_urls:
                skipped += 1
                continue
            seen_urls.add(article_url)

            description = article_data.get("description", "")
            if not isinstance(description, str):
                description = ""

            description = BeautifulSoup(
                description, "html.parser"
            ).get_text(" ", strip=True)[:300]

            article = Article(
                title=title,
                source=source,
                url=article_url,
                description=description,
                niche=niche,
                published_at=published_at,
            )

            db.add(article)
            saved += 1

        db.commit()
    finally:
        db.close()

    logger.info(f"{source} - {niche}: Saved {saved}, Skipped {skipped}")

async def main():
    for rss_source in RSS_SOURCES:
        await collect_rss(**rss_source)


if __name__ == "__main__":
    asyncio.run(main())