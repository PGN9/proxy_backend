from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()
MODEL_BACKEND_URL = "https://vader-backend-po5q.onrender.com/predict"  # the URL where vader-backend is deployed

class TextRequest(BaseModel):
    text: str

@app.get("/")
def root():
    return {"message": "proxy backend is running."}

@app.post("/analyze")
def analyze_sentiment(request: TextRequest):
    try:
        response = requests.post(MODEL_BACKEND_URL, json={"text": request.text})
        response.raise_for_status()
        return {"source": "proxy_backend", "model_response": response.json()}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error calling vader_backend: {e}")
