import re
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


NUMBER_PATTERN = re.compile(r"\d|%|₹|\$|\brs\b|\bcrore\b|\bmillion\b|\bbillion\b")
EVENT_TERMS = ("launch", "raises", "raise", "acquires", "acquire", "bans", "ban", "cuts", "cut")
LOCAL_TERMS = ("india", "indian", "karnataka", "bengaluru", "bangalore", "kannada", "rupee", "₹")
PRACTICAL_TERMS = ("how to", "apply", "deadline", "grant", "jobs", "tool", "scheme")


def _article_text(article):
    title = getattr(article, "title", "")
    description = getattr(article, "description", "")
    return f"{title if isinstance(title, str) else ''} {description if isinstance(description, str) else ''}".lower()


def _item(priority, question, source_type, reason):
    return {
        "priority": priority,
        "question": question,
        "source_type": source_type,
        "reason": reason,
    }

async def fetch_article_text(url):
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
    except httpx.HTTPError as error:
        logger.error(f"Could not fetch article: {type(error).__name__}: {error}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = soup.get_text(" ", strip=True)

    return text


def build_research_checklist(article):
    text = _article_text(article)
    niche = getattr(article, "niche", "")
    niche = niche.lower() if isinstance(niche, str) else ""

    items = [
        _item(
            "high",
            "What exactly happened, when, and who confirmed it?",
            "Original publisher and primary announcement",
            "The RSS description is only a short summary.",
        )
    ]

    if NUMBER_PATTERN.search(text):
        items.append(
            _item(
                "high",
                "What is the exact number, unit, currency, and time period?",
                "Official report, filing, or announcement",
                "Numbers in headlines and summaries need source confirmation.",
            )
        )

    if any(term in text for term in EVENT_TERMS):
        items.append(
            _item(
                "high",
                "Is there an official announcement, filing, or regulator statement confirming the event?",
                "Primary source",
                "Event-driven claims should be confirmed beyond the RSS summary.",
            )
        )

    niche_items = {
        "technology": _item(
            "medium",
            "What are the product availability, pricing, limitations, and privacy or security implications?",
            "Product documentation and official announcement",
            "Technology stories need practical context before scripting.",
        ),
        "business": _item(
            "medium",
            "What is the business impact, who benefits, and what opportunity or risk does this create?",
            "Company statement, filing, or market report",
            "Business stories need a clear audience takeaway.",
        ),
        "startups": _item(
            "medium",
            "What are the funding details, investors, company stage, and audience opportunity?",
            "Company announcement and investor or funding source",
            "Startup claims need funding and opportunity context.",
        ),
        "geopolitics": _item(
            "medium",
            "Who are the parties involved, what is the timeline, and what is confirmed versus still developing?",
            "Official statements and reputable reporting",
            "Geopolitical stories need careful status and context checks.",
        ),
    }
    if niche in niche_items:
        items.append(niche_items[niche])

    has_local_relevance = any(term in text for term in LOCAL_TERMS)
    has_practical_value = any(term in text for term in PRACTICAL_TERMS)
    if has_local_relevance or has_practical_value:
        questions = []
        if has_local_relevance:
            questions.append("What is the specific India or Karnataka relevance?")
        if has_practical_value:
            questions.append("What are the eligibility, cost, deadline, and concrete action for the audience?")

        items.append(
            _item(
                "medium",
                " ".join(questions),
                "Official local source, eligibility page, or programme details",
                "Local relevance and practical advice should be verified before presenting them.",
            )
        )

    return {
        "article_id": getattr(article, "id", None),
        "headline": getattr(article, "title", ""),
        "source_url": getattr(article, "url", ""),
        "niche": niche,
        "verification_items": items[:5],
        "script_ready": False,
    }
async def research_article(article):
    checklist = build_research_checklist(article)
    article_text = await fetch_article_text(article.url)

    return {
        "checklist": checklist,
        "article_text": article_text,
    }

async def generate_research_brief(article):
    checklist = build_research_checklist(article)
    article_text = await fetch_article_text(article.url)

    if not article_text:
        return None

    prompt = f"""
You are a fact-checking research assistant.

Analyze the article below using the research checklist.

Article:
{article_text[:12000]}

Research checklist:
{checklist["verification_items"]}

Return a concise research brief containing:
1. Confirmed facts
2. Important numbers and names
3. Primary source or evidence mentioned in the article
4. India/Karnataka relevance if applicable
5. Practical takeaway if applicable
6. Uncertain or unverified claims

Do not invent information. If something cannot be confirmed from the article, clearly say so.
"""

    from app.services.ai_service import generate_ai_response

    ai_result = await generate_ai_response(prompt)

    return {
        "article_id": article.id,
        "headline": article.title,
        "research_checklist": checklist,
        "research": ai_result,
    }