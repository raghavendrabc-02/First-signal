from types import SimpleNamespace

from app.services.article_service import get_target_articles


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


def test_get_target_articles_fetches_and_filters_articles():
    articles = [
        SimpleNamespace(niche="technology"),
        SimpleNamespace(niche="sports"),
        SimpleNamespace(niche="BUSINESS"),
    ]
    db = FakeSession(articles)

    result = get_target_articles(db)

    assert result == [articles[0], articles[2]]
    assert db.statement is not None


def test_get_target_articles_returns_an_empty_list_when_no_articles_match():
    db = FakeSession([SimpleNamespace(niche="sports")])

    assert get_target_articles(db) == []
