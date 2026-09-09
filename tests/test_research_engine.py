from types import SimpleNamespace

import pytest

from app.research.research_engine import build_research_checklist


def article(**values):
    defaults = {
        "id": 1,
        "title": "A news story",
        "description": "",
        "url": "https://example.com/article",
        "niche": "technology",
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def questions(checklist):
    return " ".join(item["question"] for item in checklist["verification_items"])


def test_checklist_always_includes_core_claim_verification():
    checklist = build_research_checklist(article())

    assert checklist["article_id"] == 1
    assert checklist["headline"] == "A news story"
    assert checklist["script_ready"] is False
    assert "What exactly happened" in questions(checklist)


@pytest.mark.parametrize("title", ["Startup raises ₹10 crore", "Sales grow 25%"])
def test_checklist_adds_number_verification(title):
    checklist = build_research_checklist(article(title=title))

    assert "exact number, unit, currency, and time period" in questions(checklist)


@pytest.mark.parametrize("title", ["Company launches new app", "Government bans imports"])
def test_checklist_adds_primary_source_verification_for_events(title):
    checklist = build_research_checklist(article(title=title))

    assert "official announcement, filing, or regulator statement" in questions(checklist)


@pytest.mark.parametrize(
    ("niche", "expected_text"),
    [
        ("technology", "product availability"),
        ("business", "business impact"),
        ("startups", "funding details"),
        ("geopolitics", "parties involved"),
    ],
)
def test_checklist_adds_niche_specific_verification(niche, expected_text):
    checklist = build_research_checklist(article(niche=niche))

    assert expected_text in questions(checklist)


def test_checklist_adds_local_and_practical_verification():
    checklist = build_research_checklist(
        article(title="How to apply for a Karnataka startup grant")
    )

    checklist_questions = questions(checklist)
    assert "India or Karnataka relevance" in checklist_questions
    assert "eligibility, cost, deadline, and concrete action" in checklist_questions


def test_checklist_limits_verification_items_to_five():
    checklist = build_research_checklist(
        article(
            title="How to apply for ₹10 crore Karnataka startup grant after company launches tool",
            niche="startups",
        )
    )

    assert len(checklist["verification_items"]) == 5
