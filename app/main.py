from fastapi import FastAPI
from fastapi import Depends
from app.database.connection import get_db

app = FastAPI()

@app.get("/test-db")
def test_db(db = Depends(get_db)):
    return {"message": "Database dependency works"}

