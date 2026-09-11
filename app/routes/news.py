from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.article import Article
from app.ranking.ranker import select_best_article
from app.schemas.article import ArticleResponse, ScriptResponse
from app.services.article_service import generate_article_script


router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok"}


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
async def generate_article_script_endpoint(
    article_id: int,
    db: Session = Depends(get_db),
):
    result, error = await generate_article_script(db, article_id)

    if error == "Article not found":
        raise HTTPException(status_code=404, detail=error)

    if error:
        raise HTTPException(status_code=502, detail=error)

    return result