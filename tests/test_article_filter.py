from types import SimpleNamespace

import pytest

from app.filters.article_filter import filter_articles, is_target_article


@pytest.mark.parametrize(
    "niche",
    ["technology", "business", "startups", "geopolitics"],
)
def test_is_target_article_accepts_target_niches(niche):
    assert is_target_article(SimpleNamespace(niche=niche)) is True


@pytest.mark.parametrize(
    "niche",
    ["Technology", "BUSINESS", "Startups", "Geopolitics"],
)
def test_is_target_article_accepts_different_capitalization(niche):
    assert is_target_article(SimpleNamespace(niche=niche)) is True


@pytest.mark.parametrize("niche", ["sports", "entertainment", ""])
def test_is_target_article_rejects_non_target_niches(niche):
    assert is_target_article(SimpleNamespace(niche=niche)) is False


@pytest.mark.parametrize(
    "article",
    [SimpleNamespace(), SimpleNamespace(niche=None), SimpleNamespace(niche=123)],
)
def test_is_target_article_rejects_missing_or_invalid_niche(article):
    assert is_target_article(article) is False


def test_filter_articles_returns_only_target_articles():
    articles = [
        SimpleNamespace(niche="technology"),
        SimpleNamespace(niche="sports"),
        SimpleNamespace(niche="BUSINESS"),
        SimpleNamespace(niche=None),
        SimpleNamespace(niche="geopolitics"),
    ]

    filtered_articles = filter_articles(articles)

    assert filtered_articles == [articles[0], articles[2], articles[4]]
