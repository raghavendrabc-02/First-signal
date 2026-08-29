from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"Message": "FirstSignal is running"}