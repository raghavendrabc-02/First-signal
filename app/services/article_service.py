from sqlalchemy import select

from app.filters.article_filter import filter_articles
from app.models.article import Article


def get_target_articles(db):
    articles = db.scalars(select(Article)).all()
    return filter_articles(articles)
