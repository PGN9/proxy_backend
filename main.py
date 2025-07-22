from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()
BACKEND_A_URL = "https://vader-backend-po5q.onrender.com"  # the URL where vader-backend is deployed

class TextRequest(BaseModel):
    text: str

@app.post("/analyze")
def analyze_sentiment(request: TextRequest):
    try:
        response = requests.post(BACKEND_A_URL, json={"text": request.text})
        response.raise_for_status()
        return {"source": "proxy_backend", "model_response": response.json()}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error calling vader_backend: {e}")
