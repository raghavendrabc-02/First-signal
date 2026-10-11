from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.article import Article


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    with TestSession() as db:
        db.add(
            Article(
                id=2,
                title="Google launches Fitbit Air in India",
                source="TechCrunch",
                url="https://example.com/fitbit-air",
                description="",
                niche="technology",
                published_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        db.commit()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_get_news(client):
    response = client.get("/news")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Database session received"
    }

def test_get_best_news(client):
    response = client.get("/news/best")

    assert response.status_code == 200

    data = response.json()

    assert "id" in data
    assert "title" in data
    assert "source" in data
    assert "url" in data

@patch(
    "app.routes.news.generate_article_script",
    new_callable=AsyncMock,
)
def test_generate_article_script(mock_generate_article_script, client):
    mock_generate_article_script.return_value = (
        {
            "article_id": 2,
            "title": "Test article",
            "script": "Fake Kannada script",
        },
        None,
    )

    response = client.post("/news/2/script")

    assert response.status_code == 200

    data = response.json()

    assert data["article_id"] == 2
    assert data["script"] == "Fake Kannada script"


def test_generate_article_script_article_not_found(client):
    response = client.post("/news/999999/script")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Article not found"
    }


@patch(
    "app.routes.news.generate_article_script",
    new_callable=AsyncMock,
)
def test_generate_article_script_research_failure(mock_generate_article_script, client):
    mock_generate_article_script.return_value = (
        None,
        "Could not generate research brief",
    )

    response = client.post("/news/2/script")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not generate research brief"
    }
