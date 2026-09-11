import re
from datetime import datetime, timezone


TARGET_NICHE_SCORES = {
    "technology": 7,
    "business": 7,
    "startups": 7,
    "geopolitics": 5,
}

LOCAL_TERMS = (
    "india",
    "indian",
    "karnataka",
    "bengaluru",
    "bangalore",
    "kannada",
    "rupee",
    "₹",
)
AUDIENCE_TERMS = ("jobs", "hiring", "education", "consumer", "small business")
HOOK_EVENT_TERMS = (
    "launches",
    "raises",
    "bans",
    "cuts",
    "acquires",
    "wins",
    "fails",
)
NOTABLE_ENTITY_TERMS = (
    "google",
    "apple",
    "microsoft",
    "openai",
    "meta",
    "amazon",
    "tesla",
    "reliance",
    "tcs",
    "infosys",
    "government",
    "india",
    "china",
    "united states",
)
CONSEQUENCE_TERMS = ("what changes", "after", "amid", "could", "will", "why", "how")
VAGUE_HOOK_TERMS = ("everything you need to know", "watch live", "live updates")
PRACTICAL_PRODUCT_TERMS = (
    "tool",
    "app",
    "ai",
    "platform",
    "software",
    "service",
    "scheme",
)
ACTIONABLE_TERMS = ("how to", "guide", "tips", "apply", "deadline", "pricing", "eligibility")
OPPORTUNITY_TERMS = ("funding", "grant", "hiring", "jobs", "startup", "launches")
IMPORTANCE_POLICY_TERMS = (
    "government",
    "regulation",
    "regulatory",
    "law",
    "court",
    "budget",
    "central bank",
    "election",
)
IMPORTANCE_IMPACT_TERMS = (
    "inflation",
    "jobs",
    "markets",
    "cybersecurity",
    "conflict",
    "war",
    "acquisition",
    "acquires",
)
TRUSTED_SOURCES = {"BBC News", "The Guardian", "Reuters"}


def _text(article):
    title = getattr(article, "title", "")
    description = getattr(article, "description", "")
    return f"{title if isinstance(title, str) else ''} {description if isinstance(description, str) else ''}".lower()


def _contains_any(text, terms):
    return any(term in text for term in terms)


def _cap_score(score):
    return max(0, min(score, 10))


def calculate_freshness_score(article, now=None):
    published_at = getattr(article, "published_at", None)
    if not isinstance(published_at, datetime):
        return 0

    now = now or datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_in_hours = max(0, (now - published_at).total_seconds() / 3600)
    if age_in_hours <= 2:
        return 10
    if age_in_hours <= 6:
        return 9
    if age_in_hours <= 12:
        return 8
    if age_in_hours <= 24:
        return 7
    if age_in_hours <= 48:
        return 5
    if age_in_hours <= 72:
        return 3
    return 1


def calculate_audience_relevance_score(article):
    niche = getattr(article, "niche", "")
    score = TARGET_NICHE_SCORES.get(niche.lower(), 0) if isinstance(niche, str) else 0
    text = _text(article)

    if _contains_any(text, LOCAL_TERMS):
        score += 2
    if _contains_any(text, AUDIENCE_TERMS):
        score += 1

    return _cap_score(score)


def calculate_hook_potential_score(article):
    title = getattr(article, "title", "")
    if not isinstance(title, str) or not title.strip():
        return 0

    headline = title.lower()
    score = 1

    if re.search(r"\d|%|₹|\$|\brs\b|\bcrore\b|\bmillion\b|\bbillion\b", headline):
        score += 3
    if _contains_any(headline, HOOK_EVENT_TERMS):
        score += 2
    if _contains_any(headline, NOTABLE_ENTITY_TERMS):
        score += 2
    if _contains_any(headline, LOCAL_TERMS):
        score += 1
    if _contains_any(headline, CONSEQUENCE_TERMS):
        score += 1
    if 45 <= len(title.strip()) <= 110:
        score += 1
    if _contains_any(headline, VAGUE_HOOK_TERMS):
        score -= 2

    return _cap_score(score)


def calculate_practical_value_score(article):
    text = _text(article)
    score = 0

    if _contains_any(text, PRACTICAL_PRODUCT_TERMS):
        score += 4
    if _contains_any(text, ACTIONABLE_TERMS):
        score += 3
    if _contains_any(text, OPPORTUNITY_TERMS):
        score += 2
    if _contains_any(text, LOCAL_TERMS):
        score += 1

    return _cap_score(score)


def calculate_importance_score(article):
    text = _text(article)
    score = 0

    if _contains_any(text, IMPORTANCE_POLICY_TERMS):
        score += 4
    if _contains_any(text, IMPORTANCE_IMPACT_TERMS):
        score += 3
    if re.search(r"\d|%|₹|\$|\bcrore\b|\bmillion\b|\bbillion\b", text):
        score += 2
    if getattr(article, "source", "") in TRUSTED_SOURCES:
        score += 1

    return _cap_score(score)


def calculate_weighted_score(article, now=None):
    return (
        calculate_freshness_score(article, now) * 0.25
        + calculate_audience_relevance_score(article) * 0.25
        + calculate_hook_potential_score(article) * 0.30
        + calculate_practical_value_score(article) * 0.15
        + calculate_importance_score(article) * 0.05
    )


def _published_sort_value(article):
    published_at = getattr(article, "published_at", None)
    if not isinstance(published_at, datetime):
        return float("-inf")
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.timestamp()

def rank_articles(articles, now=None):
    return sorted(
        articles,
        key=lambda article: (
            calculate_weighted_score(article, now),
            calculate_hook_potential_score(article),
            calculate_freshness_score(article, now),
            _published_sort_value(article),
        ),
        reverse=True,
    )

def select_best_article(articles, now=None):
    articles = list(articles)
    if not articles:
        return None

    return max(
        articles,
        key=lambda article: (
            calculate_weighted_score(article, now),
            calculate_hook_potential_score(article),
            calculate_freshness_score(article, now),
            _published_sort_value(article),
        ),
    )
