from types import SimpleNamespace

import pytest

from app.filters.topic_dedup import (
    extract_keywords,
    extract_title_keywords,
    find_covered_story,
    is_same_story,
    normalize_url,
)


def article(title, url="https://example.com/story"):
    return SimpleNamespace(title=title, url=url)


FITBIT_TECHCRUNCH = article(
    "Google launches Fitbit Air in India, though its high price might deter the masses",
    "https://techcrunch.com/2026/09/30/google-launches-fitbit-air-in-india/",
)


def test_normalize_url_ignores_tracking_params_scheme_and_trailing_slash():
    assert normalize_url("https://www.Example.com/a/b/?utm_source=rss#top") == (
        normalize_url("http://example.com/a/b")
    )


def test_extract_keywords_drops_stopwords_and_generic_words():
    assert extract_keywords("Apple launches the new iPhones in India") == {
        "apple",
        "iphone",
        "india",
    }


def test_duplicate_url_is_same_story_even_with_different_title():
    first = article("Original headline", "https://site.com/story?utm_medium=rss")
    second = article("Completely rewritten headline", "https://www.site.com/story/")

    assert is_same_story(second, first)


@pytest.mark.parametrize(
    "title",
    [
        "Fitbit Air arrives in India at Rs 9,999",
        "Google's Fitbit Air goes on sale in India with a steep price tag",
        "Fitbit Air launched in India: price, features and availability",
    ],
)
def test_different_url_same_story_is_duplicate(title):
    candidate = article(title, "https://another-publisher.com/fitbit-air-india")

    assert is_same_story(candidate, FITBIT_TECHCRUNCH)


@pytest.mark.parametrize(
    ("first_title", "second_title"),
    [
        (
            "Apple launches iPhone 18 Pro with bigger battery",
            "Apple faces EU fine over App Store payment rules",
        ),
        (
            "Apple cuts iPhone prices in India",
            "Apple opens new store in Bengaluru, India",
        ),
        (
            "OpenAI launches visual ads alongside image generation results",
            "OpenAI cuts ties with 3 safety researchers, WSJ reports",
        ),
        (
            "Google launches Fitbit Air in India, though its high price might deter the masses",
            "Google fined in India over Android antitrust case",
        ),
    ],
)
def test_different_stories_about_same_company_are_not_duplicates(
    first_title, second_title
):
    first = article(first_title, "https://a.com/1")
    second = article(second_title, "https://b.com/2")

    assert not is_same_story(second, first)
    assert not is_same_story(first, second)


def test_find_covered_story_returns_matching_delivered_article():
    unrelated = article("Euro falls to 17-month low against dollar", "https://a.com/euro")
    candidate = article("Fitbit Air arrives in India at Rs 9,999", "https://b.com/fitbit")

    assert find_covered_story(candidate, [unrelated, FITBIT_TECHCRUNCH]) is FITBIT_TECHCRUNCH
    assert find_covered_story(unrelated, [FITBIT_TECHCRUNCH]) is None


def test_missing_fields_are_not_duplicates():
    assert not is_same_story(article(None, None), article(None, None))


# Regression cases taken from real FirstSignal headlines (run 37441924288).
@pytest.mark.parametrize(
    ("first_title", "second_title"),
    [
        (
            "AI voice startup ElevenLabs doubles valuation to $22B",
            "Valor, Atreides, and Sequoia back AI startup Flow Engineering at $750M valuation",
        ),
        (
            "Chinese AI tool told researchers how to make bioweapons",
            "Pentagon stops using Anthropic AI tools after blacklisting company, BBC told",
        ),
        (
            "Chinese AI tool told researchers how to make bioweapons",
            "Researchers are tracking a Chinese AI ‘agent fleet’",
        ),
        (
            "The Week’s 10 Biggest Funding Rounds: Almost All About AI",
            "The Week’s 10 Biggest Funding Rounds: Cybersecurity, AI And Health Take The Lead",
        ),
        (
            "Energy bills are rising by £60 a year - here's how you can bring that down",
            "What is Burnham’s GB Grid plan and could it bring down energy bills?",
        ),
        (
            "Open or closed AI? How founders are choosing what to build on at TechCrunch Disrupt 2026",
            "TechCrunch Disrupt 2026: Blackstone’s Jas Khaira on building the next generation of AI giants",
        ),
        (
            "All the AI agents that can live in your text messages",
            "DoorDash launches an AI agent you can text to order food",
        ),
    ],
)
def test_reported_false_positives_are_not_duplicates(first_title, second_title):
    first = article(first_title, "https://a.com/1")
    second = article(second_title, "https://b.com/2")

    assert not is_same_story(second, first)
    assert not is_same_story(first, second)


@pytest.mark.parametrize(
    ("first_title", "second_title"),
    [
        (
            "Greggs announces plans to shut four UK factories that could cost 740 jobs",
            "Greggs to cut 740 jobs and close factories",
        ),
        (
            "Christa Pike's prognosis still unclear after failed execution, lawyer says",
            "Tennessee prison chief to resign after Christa Pike's failed execution",
        ),
        (
            "G7 to release millions of barrels of oil and diesel after Trump threat",
            "G7 to release up to 100m barrels of emergency oil and diesel reserves",
        ),
        (
            "OpenAI safety employee resigns, claiming the company’s ‘culture is broken’",
            "OpenAI safety leader quits, warning AI company’s culture is ‘broken’",
        ),
        (
            "Spotify billionaire’s body scan startup has come to America",
            "Is Neko Health’s body scan worth it? Spotify billionaire’s startup has come to America",
        ),
        (
            "Should cockpits stay locked from the inside? Flydubai stabbing raises flight security questions",
            "What we know about stabbing on Flydubai flight to Israel",
        ),
    ],
)
def test_reported_true_duplicates_still_match(first_title, second_title):
    first = article(first_title, "https://a.com/1")
    second = article(second_title, "https://b.com/2")

    assert is_same_story(second, first)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Who’ll win? We’re live", {"win"}),
        ("Spain's housing crisis", {"spain", "housing", "crisis"}),
        ("Flydubai co-pilot attacked", {"flydubai", "copilot", "attacked"}),
        ("Société Générale cuts 900 jobs", {"société", "générale", "cut", "900", "job"}),
        ("Q3 2026: AI funding hits $100bn", {"q3", "funding", "100bn"}),
        ("Burnham’s triple lock gamble | Politics Weekly", {"burnham", "triple", "lock", "gamble", "politic", "weekly"}),
    ],
)
def test_extract_keywords_handles_punctuation_accents_and_years(text, expected):
    assert extract_keywords(text) == expected


def test_series_suffix_and_recurring_prefix_are_ignored_for_matching():
    assert extract_title_keywords("Burnham’s triple lock gamble | Politics Weekly") == {
        "burnham",
        "triple",
        "lock",
        "gamble",
    }
    assert extract_title_keywords(
        "The Week’s 10 Biggest Funding Rounds: Cybersecurity, AI And Health Take The Lead"
    ) == {"cybersecurity", "health", "lead"}


def test_short_headlines_only_match_by_url():
    first = article("Business Daily", "https://bbc.example/business-daily/1")
    second = article("Business Daily", "https://bbc.example/business-daily/2")

    assert not is_same_story(second, first)


def test_normalize_url_keeps_path_case():
    assert normalize_url("https://site.com/Story/A") != normalize_url("https://site.com/story/a")
