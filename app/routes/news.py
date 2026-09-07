from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db

router = APIRouter()


@router.get("/news")
def get_news(db: Session = Depends(get_db)):
    return {"message": "Database session received"}