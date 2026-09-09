import os
from datetime import datetime, timezone

os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.models.article import Article
from app.routes import news


class FakeScalarResult:
    def __init__(self, articles):
        self.articles = articles

    def all(self):
        return self.articles


class FakeSession:
    def __init__(self, articles):
        self.articles = articles
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return FakeScalarResult(self.articles)


def create_client(db):
    app = FastAPI()
    app.include_router(news.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_get_best_news_returns_the_selected_article(monkeypatch):
    first_article = Article(
        id=1,
        title="First article",
        source="BBC News",
        url="https://example.com/first",
        description="First description",
        niche="technology",
        published_at=datetime(2026, 9, 7, 10, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 7, 10, 5, tzinfo=timezone.utc),
    )
    best_article = Article(
        id=2,
        title="Best article",
        source="The Guardian",
        url="https://example.com/best",
        description="Best description",
        niche="business",
        published_at=datetime(2026, 9, 7, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 9, 7, 11, 5, tzinfo=timezone.utc),
    )
    db = FakeSession([first_article, best_article])
    selected_articles = []

    def select_article(articles):
        selected_articles.extend(articles)
        return best_article

    monkeypatch.setattr(news, "select_best_article", select_article)

    response = create_client(db).get("/news/best")

    assert response.status_code == 200
    assert response.json() == {
        "id": 2,
        "title": "Best article",
        "source": "The Guardian",
        "url": "https://example.com/best",
        "description": "Best description",
        "niche": "business",
        "published_at": "2026-09-07T11:00:00Z",
        "created_at": "2026-09-07T11:05:00Z",
    }
    assert selected_articles == [first_article, best_article]
    assert db.statement is not None


def test_get_best_news_returns_not_found_when_no_articles_exist():
    response = create_client(FakeSession([])).get("/news/best")

    assert response.status_code == 404
    assert response.json() == {"detail": "No articles available"}
