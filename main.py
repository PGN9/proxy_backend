from fastapi import FastAPI, HTTPException
from typing import List
from dotenv import load_dotenv
import httpx
import json
import os
import time

load_dotenv()

app = FastAPI()
MODEL_BACKEND_URL = "https://vader-backend-po5q.onrender.com/predict"  # the URL where vader-backend is deployed

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

TEXTS_TABLE = "comments"

request_count = 0
start_time = time.time()


# for updating the table when we get result back
async def upsert(table, data, conflict_field):
    """Upsert a record into Supabase table"""
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {"on_conflict": conflict_field}
        #Upserting data into table
        response = await client.post(url,
                                     headers=HEADERS,
                                     params=params,
                                     data=json.dumps(data))
        if response.status_code >= 400:
            print(
                f"❌ Failed to upsert into {table}: {response.status_code} - {response.text}"
            )


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.get("/analyze")
async def analyze_sentiment():
    # Step 1: fetch id and body from Supabase
    url = f"{SUPABASE_URL}/rest/v1/{TEXTS_TABLE}?select=id,body"

    async with httpx.AsyncClient() as client:
        try:
            fetch_start = time.time()
            supa_resp = await client.get(url, headers=HEADERS)
            supa_resp.raise_for_status()
            comments_data = supa_resp.json()
            fetch_end = time.time()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502,
                                detail=f"Error fetching from Supabase: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=supa_resp.status_code,
                detail=f"Supabase returned error: {supa_resp.text}")

    # Prepare payload with id and body
    comments = [{
        "id": item["id"],
        "body": item["body"]
    } for item in comments_data if "id" in item and "body" in item]

    if not comments:
        return {"message": "No comments found in Supabase."}

    # Step 2: send to vader backend
    payload = {"comments": comments}

    async with httpx.AsyncClient() as client:
        try:
            send_start = time.time()
            model_resp = await client.post(MODEL_BACKEND_URL, json=payload)
            model_resp.raise_for_status()
            send_end = time.time()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502,
                                detail=f"Error calling model backend: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=model_resp.status_code,
                detail=f"Model backend returned error: {model_resp.text}")

    model_results = model_resp.json()

    # update Supabase with sentiment results
    update_count = 0
    for res in model_results["results"]:
        update_data = {
            "id": res["id"],
            "sentiment": res.get("sentiment"),
            "sentiment_score": res.get("sentiment_score")
        }
        success = await upsert(TEXTS_TABLE, update_data, "id")
        if success:
            update_count += 1

    # timing info
    timings = {
        "supabase_fetch_time":
        fetch_end - fetch_start,
        "model_send_time":
        send_end - send_start,
        "model_processing_time":
        model_resp.elapsed.total_seconds()
        if hasattr(model_resp, "elapsed") else None,
        "total_time": (send_end - fetch_start)
    }

    return {
        "source": "proxy_backend",
        "number_of_comments": len(comments),
        "number_updated": update_count,
        "model_response": model_results,
        "timing": timings
    }
