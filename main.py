from fastapi import FastAPI, HTTPException
from typing import List
from dotenv import load_dotenv
import httpx
import json
import os
import time

load_dotenv()

app = FastAPI()
MODEL_BACKEND_URL = "https://vader-backend-po5q.onrender.com/predict"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")

HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}

TEXTS_TABLE = "comments"


async def batch_upsert(table, data_list, conflict_field):
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {"on_conflict": conflict_field}
        response = await client.post(
            url,
            headers=HEADERS,
            params=params,
            json=data_list  # let httpx handle the encoding
        )
        if response.status_code >= 400:
            print(
                f"❌ Failed batch upsert into {table}: {response.status_code} - {response.text}"
            )
            return False
        return True


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.get("/analyze")
async def analyze_sentiment():
    timings = {}
    overall_start = time.perf_counter()

    # Step 1: fetch id and body from Supabase
    fetch_start = time.perf_counter()
    url = f"{SUPABASE_URL}/rest/v1/{TEXTS_TABLE}?select=id,body"
    async with httpx.AsyncClient() as client:
        try:
            supa_resp = await client.get(url, headers=HEADERS)
            supa_resp.raise_for_status()
            comments_data = supa_resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502,
                                detail=f"Error fetching from Supabase: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=supa_resp.status_code,
                detail=f"Supabase returned error: {supa_resp.text}")
    fetch_end = time.perf_counter()
    timings["supabase_fetch_time"] = fetch_end - fetch_start

    # Prepare payload with id and body
    comments = [{
        "id": item["id"],
        "body": item["body"]
    } for item in comments_data if "id" in item and "body" in item]
    if not comments:
        return {"message": "No comments found in Supabase."}

    # Step 2: send to vader backend
    send_start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        try:
            model_resp = await client.post(MODEL_BACKEND_URL,
                                           json={"comments": comments})
            model_resp.raise_for_status()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502,
                                detail=f"Error calling model backend: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=model_resp.status_code,
                detail=f"Model backend returned error: {model_resp.text}")
    send_end = time.perf_counter()
    timings["model_send_time"] = send_end - send_start

    # Model internal processing time if available
    timings["model_processing_time"] = model_resp.elapsed.total_seconds(
    ) if hasattr(model_resp, "elapsed") else None

    model_results = model_resp.json()

    # Step 3: update Supabase with sentiment results
    update_start = time.perf_counter()

    update_data_list = [{
        "id": res["id"],
        "sentiment": res.get("sentiment"),
        "sentiment_score": res.get("sentiment_score")
    } for res in model_results["results"]]

    success = await batch_upsert(TEXTS_TABLE, update_data_list, "id")
    update_count = len(update_data_list) if success else 0

    update_end = time.perf_counter()
    timings["supabase_update_time"] = update_end - update_start

    overall_end = time.perf_counter()
    timings["total_time"] = overall_end - overall_start

    return {
        "source": "proxy_backend",
        "number_of_comments": len(comments),
        "number_updated": update_count,
        "model_response": model_results,
        "timing": timings
    }
