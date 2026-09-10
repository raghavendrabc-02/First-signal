from sqlalchemy import select

from app.filters.article_filter import filter_articles
from app.models.article import Article

from app.research.research_engine import generate_research_brief
from app.services.script_service import generate_script


def get_target_articles(db):
    articles = db.scalars(select(Article)).all()
    return filter_articles(articles)


async def generate_article_script(db, article_id):
    article = db.get(Article, article_id)

    if article is None:
        return None, "Article not found"

    research_result = await generate_research_brief(article)

    if research_result is None:
        return None, "Could not generate research brief"

    script = await generate_script(
        article,
        research_result["research"],
    )

    if script is None:
        return None, "Could not generate script"

    return {
        "article_id": article.id,
        "title": article.title,
        "script": script,
    }, None