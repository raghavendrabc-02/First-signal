from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.article import Article
from app.ranking.ranker import select_best_article
from app.schemas.article import ArticleResponse, ScriptResponse

from app.research.research_engine import generate_research_brief
from app.services.script_service import generate_script

router = APIRouter()


@router.get("/news")
def get_news(db: Session = Depends(get_db)):
    return {"message": "Database session received"}


@router.get("/news/best", response_model=ArticleResponse)
def get_best_news(db: Session = Depends(get_db)):
    articles = db.scalars(select(Article)).all()
    best_article = select_best_article(articles)

    if best_article is None:
        raise HTTPException(status_code=404, detail="No articles available")

    return best_article

@router.post("/news/{article_id}/script", response_model=ScriptResponse)
async def generate_article_script(
    article_id: int,
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    research_result = await generate_research_brief(article)

    if research_result is None:
        raise HTTPException(
            status_code=502,
            detail="Could not generate research brief",
        )

    script = await generate_script(
        article,
        research_result["research"],
    )

    if script is None:
        raise HTTPException(
            status_code=502,
            detail="Could not generate script",
        )

    return {
        "article_id": article.id,
        "title": article.title,
        "script": script,
    }