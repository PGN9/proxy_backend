from fastapi import FastAPI, Request
from pydantic import BaseModel
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List
import os
import time

request_count = 0
start_time = time.time()

app = FastAPI()
analyzer = SentimentIntensityAnalyzer()

# Accept a list of texts instead of a single string
class TextListRequest(BaseModel):
    texts: List[str]

@app.get("/")
def root():
    return {"message": "vader backend is running."}

@app.post("/predict")
def predict_sentiment(request: TextListRequest):
    results = []
    for text in request.texts:
        scores = analyzer.polarity_scores(text)
        sentiment = (
            "positive" if scores["compound"] > 0.05 else
            "negative" if scores["compound"] < -0.05 else
            "neutral"
        )
        results.append({
            "text": text,
            "sentiment": sentiment,
            "compound": scores["compound"]
        })
    return results

@app.middleware("http")
async def count_requests(request: Request, call_next):
    global request_count, start_time
    request_count += 1
    response = await call_next(request)

    elapsed = time.time() - start_time
    if elapsed > 10:
        print(f"[Request Stats] Last 10s - Requests: {request_count}, RPS: {request_count / elapsed:.2f}", flush=True)
        request_count = 0
        start_time = time.time()

    return response

# For Render or local deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
