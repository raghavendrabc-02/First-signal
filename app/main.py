from fastapi import FastAPI
from fastapi import Depends
from app.database.connection import get_db
from app.routes.news import router as news_router
app = FastAPI()
app.include_router(news_router)

@app.get("/test_db") 
def test_db(db = Depends(get_db)):
    return {"message": "Database dependency works"}

