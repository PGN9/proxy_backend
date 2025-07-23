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
    payload = {"texts": request.texts}

    # Get the number of comments
    num_comments = len(request.texts)

    # Total round trip timer start
    total_start = time.time()

    # Send to vader-backend timer
    send_start = time.time()

    try:
        response = requests.post(MODEL_BACKEND_URL, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=502,
                            detail=f"Error calling vader_backend: {e}")
    
    # sent
    send_end = time.time()
    send_time = send_end - send_start

    # vader processing time
    process_time = response.elapsed.total_seconds()

    # response return time
    return_end = time.time()
    return_time = return_end - send_end

    # total round trip time
    total_time = return_end - total_start

    # return response and timings
    return {
        "source": "proxy_backend", 
        "model_response": response.json(),
        "number_of_comments": num_comments,
        "timing": {
            "send_time": send_time,
            "process_time": process_time,
            "return_time": return_time,
            "total_round_trip": total_time
        }
    }