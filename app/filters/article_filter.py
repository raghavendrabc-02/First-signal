TARGET_NICHES = {
    "technology",
    "business",
    "startups",
    "geopolitics",
}


def is_target_article(article):
    niche = getattr(article, "niche", "")
    return isinstance(niche, str) and niche.lower() in TARGET_NICHES


def filter_articles(articles):
    return [article for article in articles if is_target_article(article)]
