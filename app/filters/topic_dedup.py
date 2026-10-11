import re
from urllib.parse import urlsplit


# Two headlines are treated as the same story only when they share several
# distinctive keywords. A single shared company or country (e.g. "Apple",
# "India") is never enough on its own.
MIN_SHARED_TITLE_KEYWORDS = 3
MIN_TITLE_OVERLAP = 0.4

STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "am", "amid",
    "an", "and", "any", "are", "as", "at", "be", "been", "before", "being",
    "between", "but", "by", "can", "could", "did", "do", "does", "for",
    "from", "had", "has", "have", "he", "her", "his", "how", "if", "in",
    "into", "is", "it", "its", "may", "might", "more", "most", "much", "no",
    "not", "of", "off", "on", "or", "our", "out", "over", "she", "so",
    "some", "than", "that", "the", "their", "them", "there", "these",
    "they", "this", "those", "though", "through", "to", "too", "under",
    "up", "us", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "why", "will", "with", "would", "you", "your",
}

# Words common in headlines that say nothing about which story it is.
GENERIC_NEWS_WORDS = {
    "ai", "announce", "back", "best", "biggest", "breaking", "bring", "come",
    "day", "down", "exclusive", "first", "get", "go", "goe", "hit", "know",
    "latest", "launch", "live", "make", "new", "news", "next", "now",
    "report", "review", "say", "take", "time", "today", "told", "top",
    "update", "video", "watch", "way", "week", "went", "year",
}

YEAR_PATTERN = re.compile(r"^(19|20)\d\d$")

# Possessives and contractions: "Spain's" -> "Spain", "who'll" -> "who".
CONTRACTION_PATTERN = re.compile(r"['’](s|ll|re|ve|d|t|m)\b")

# "co-pilot" -> "copilot", "sell-off" -> "selloff".
HYPHENATED_WORD_PATTERN = re.compile(r"(?<=\w)[-‐‑](?=\w)")

# Recurring series such as "The Week's 10 Biggest Funding Rounds: ...". Only
# the part after the colon identifies the specific edition.
RECURRING_SERIES_PATTERN = re.compile(
    r"\b(week['’]?s|weekly|daily|this week|roundup|round-up|biggest funding rounds)\b",
    re.IGNORECASE,
)


def normalize_url(url):
    if not isinstance(url, str):
        return ""

    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")

    return f"{host}{path}"


def _normalize_token(token):
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("ches", "shes", "sses", "xes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _story_part_of_title(title):
    # Drop column or series names after " | ", e.g. "... | Politics Weekly".
    title = title.split(" | ")[0]

    head, colon, tail = title.partition(":")
    if colon and tail.strip() and RECURRING_SERIES_PATTERN.search(head):
        return tail

    return title


def extract_keywords(text):
    if not isinstance(text, str):
        return set()

    text = CONTRACTION_PATTERN.sub("", text.lower())
    text = HYPHENATED_WORD_PATTERN.sub("", text)

    keywords = set()

    for token in re.findall(r"[^\W_]+", text):
        if len(token) < 2 or token in STOPWORDS:
            continue

        token = _normalize_token(token)

        if (
            token in STOPWORDS
            or token in GENERIC_NEWS_WORDS
            or YEAR_PATTERN.match(token)
        ):
            continue

        keywords.add(token)

    return keywords


def extract_title_keywords(title):
    if not isinstance(title, str):
        return set()

    return extract_keywords(_story_part_of_title(title))


def is_same_story(article, covered_article):
    article_url = normalize_url(getattr(article, "url", ""))

    if article_url and article_url == normalize_url(getattr(covered_article, "url", "")):
        return True

    title_keywords = extract_title_keywords(getattr(article, "title", ""))
    covered_keywords = extract_title_keywords(getattr(covered_article, "title", ""))

    shared = title_keywords & covered_keywords

    if len(shared) < MIN_SHARED_TITLE_KEYWORDS:
        return False

    overlap = len(shared) / min(len(title_keywords), len(covered_keywords))

    return overlap >= MIN_TITLE_OVERLAP


def find_covered_story(article, covered_articles):
    for covered_article in covered_articles:
        if is_same_story(article, covered_article):
            return covered_article

    return None
