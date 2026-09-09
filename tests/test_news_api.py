from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

def test_get_news():
    response = client.get("/news")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Database session received"
    }

def test_get_best_news():
    response = client.get("/news/best")

    assert response.status_code == 200

    data = response.json()

    assert "id" in data
    assert "title" in data
    assert "source" in data
    assert "url" in data

@patch(
    "app.routes.news.generate_research_brief",
    new_callable=AsyncMock,
)
@patch(
    "app.routes.news.generate_script",
    new_callable=AsyncMock,
)
def test_generate_article_script(mock_generate_script, mock_generate_research):
    mock_generate_research.return_value = {
        "research": "Fake research result"
    }

    mock_generate_script.return_value = "Fake Kannada script"

    response = client.post("/news/2/script")

    assert response.status_code == 200

    data = response.json()

    assert data["article_id"] == 2
    assert data["script"] == "Fake Kannada script"


def test_generate_article_script_article_not_found():
    response = client.post("/news/999999/script")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Article not found"
    }

@patch(
    "app.routes.news.generate_research_brief",
    new_callable=AsyncMock,
)
def test_generate_article_script_research_failure(mock_generate_research):
    mock_generate_research.return_value = None

    response = client.post("/news/2/script")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not generate research brief"
    }