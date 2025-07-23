from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List
import requests

import time

request_count = 0
start_time = time.time()

app = FastAPI()
MODEL_BACKEND_URL = "https://vader-backend-po5q.onrender.com/predict"  # the URL where vader-backend is deployed


class TextListRequest(BaseModel):
    texts: List[str]


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.post("/analyze")
def analyze_sentiment(request: TextListRequest):
    try:
        response = requests.post(MODEL_BACKEND_URL,
                                 json={"texts": request.texts})
        response.raise_for_status()
        return {"source": "proxy_backend", "model_response": response.json()}
    except requests.RequestException as e:
        raise HTTPException(status_code=502,
                            detail=f"Error calling vader_backend: {e}")


@app.middleware("http")
async def count_requests(request: Request, call_next):
    global request_count, start_time
    request_count += 1
    response = await call_next(request)

    elapsed = time.time() - start_time
    if elapsed > 60:
        print(
            f"[Request Stats] Last 60s - Requests: {request_count}, RPS: {request_count / elapsed:.2f}"
        )
        request_count = 0
        start_time = time.time()

    return response
