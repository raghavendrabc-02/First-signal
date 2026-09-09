from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.ranking import ranker


NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def article(**values):
    defaults = {
        "title": "A clear news story",
        "description": "",
        "source": "Other Source",
        "niche": "technology",
        "published_at": NOW,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize(
    ("age_hours", "expected_score"),
    [(2, 10), (6, 9), (12, 8), (24, 7), (48, 5), (72, 3), (73, 1)],
)
def test_freshness_score_uses_age_bands(age_hours, expected_score):
    item = article(published_at=NOW - timedelta(hours=age_hours))

    assert ranker.calculate_freshness_score(item, NOW) == expected_score


def test_freshness_score_returns_zero_without_a_publication_date():
    assert ranker.calculate_freshness_score(article(published_at=None), NOW) == 0


def test_audience_relevance_rewards_local_and_audience_terms():
    item = article(niche="business", title="Bengaluru jobs grow at small businesses")

    assert ranker.calculate_audience_relevance_score(item) == 10


def test_hook_potential_uses_concrete_headline_signals():
    item = article(
        title="Bengaluru startup raises ₹200 crore after OpenAI deal",
    )

    assert ranker.calculate_hook_potential_score(item) == 10


def test_hook_potential_penalizes_vague_headlines():
    item = article(title="Everything you need to know")

    assert ranker.calculate_hook_potential_score(item) == 0


def test_practical_value_rewards_actionable_opportunities():
    item = article(
        title="How to apply for Karnataka startup grant",
        description="AI tools pricing and deadline details",
    )

    assert ranker.calculate_practical_value_score(item) == 10


def test_importance_uses_policy_impact_scale_and_source_signals():
    item = article(
        title="Government budget targets 10% inflation cut",
        source="BBC News",
    )

    assert ranker.calculate_importance_score(item) == 10


def test_weighted_score_uses_the_specified_weights(monkeypatch):
    item = article()
    monkeypatch.setattr(ranker, "calculate_freshness_score", lambda *_: 10)
    monkeypatch.setattr(ranker, "calculate_audience_relevance_score", lambda *_: 8)
    monkeypatch.setattr(ranker, "calculate_hook_potential_score", lambda *_: 6)
    monkeypatch.setattr(ranker, "calculate_practical_value_score", lambda *_: 4)
    monkeypatch.setattr(ranker, "calculate_importance_score", lambda *_: 2)

    assert ranker.calculate_weighted_score(item, NOW) == pytest.approx(7.0)


def test_select_best_article_chooses_the_highest_weighted_score(monkeypatch):
    lower = article(title="Lower")
    higher = article(title="Higher")
    scores = {id(lower): 6, id(higher): 7}
    monkeypatch.setattr(
        ranker,
        "calculate_weighted_score",
        lambda item, now: scores[id(item)],
    )

    assert ranker.select_best_article([lower, higher], NOW) is higher


def test_select_best_article_breaks_ties_by_hook_then_freshness(monkeypatch):
    lower_hook = article(title="Lower hook", published_at=NOW)
    higher_hook = article(title="Higher hook", published_at=NOW - timedelta(hours=1))
    scores = {id(lower_hook): 7, id(higher_hook): 7}
    hooks = {id(lower_hook): 6, id(higher_hook): 8}
    monkeypatch.setattr(ranker, "calculate_weighted_score", lambda item, now: scores[id(item)])
    monkeypatch.setattr(ranker, "calculate_hook_potential_score", lambda item: hooks[id(item)])

    assert ranker.select_best_article([lower_hook, higher_hook], NOW) is higher_hook


def test_select_best_article_uses_newest_publication_time_as_final_tie_breaker(monkeypatch):
    older = article(title="Older", published_at=NOW - timedelta(hours=2))
    newer = article(title="Newer", published_at=NOW - timedelta(hours=1))
    monkeypatch.setattr(ranker, "calculate_weighted_score", lambda item, now: 7)
    monkeypatch.setattr(ranker, "calculate_hook_potential_score", lambda item: 7)
    monkeypatch.setattr(ranker, "calculate_freshness_score", lambda item, now: 7)

    assert ranker.select_best_article([older, newer], NOW) is newer


def test_select_best_article_returns_none_for_no_articles():
    assert ranker.select_best_article([], NOW) is None
