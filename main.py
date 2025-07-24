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
if not SUPABASE_URL or not SUPABASE_API_KEY:
    raise RuntimeError(
        "Missing Supabase credentials in environment variables.")

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


async def fetch_all_comments():
    all_comments = []
    step = 1000
    offset = 0

    async with httpx.AsyncClient() as client:
        while True:
            headers = {**HEADERS, "Range": f"{offset}-{offset + step - 1}"}
            url = f"{SUPABASE_URL}/rest/v1/{TEXTS_TABLE}?select=id,body"
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            all_comments.extend(batch)
            if len(batch) < step:
                break
            offset += step

    return all_comments


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.get("/analyze")
async def analyze_sentiment():
    try:
        timings = {}
        overall_start = time.perf_counter()

        # Step 1: fetch id and body from Supabase
        fetch_start = time.perf_counter()
        comments_data = await fetch_all_comments()
        fetch_end = time.perf_counter()
        timings["supabase_fetch_time"] = fetch_end - fetch_start

        # Prepare payload
        comments = [{
            "id": item["id"],
            "body": item["body"]
        } for item in comments_data if "id" in item and "body" in item]

        print(f"🧪 Number of comments to process: {len(comments)}")
        if not comments:
            return {"message": "No comments found in Supabase."}

        # Step 2: send to backend model
        send_start = time.perf_counter()
        async with httpx.AsyncClient() as client:
            model_resp = await client.post(
                MODEL_BACKEND_URL,
                json={"comments": comments},
                timeout=600.0  # or some higher value (seconds)
            )
            print("✅ Sent to backend, status:", model_resp.status_code)
            model_resp.raise_for_status()
        send_end = time.perf_counter()

        model_results = model_resp.json()
        if hasattr(model_resp, "elapsed"):
            model_processing_time = model_resp.elapsed.total_seconds()
        else:
            model_processing_time = None
        timings["model_processing_time"] = model_processing_time
        # Subtract processing time only if it's available
        if model_processing_time is not None:
            timings[
                "model_send_time"] = send_end - send_start - model_processing_time
        else:
            timings["model_send_time"] = send_end - send_start

        # Step 3: upsert
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
            "model_response": model_results,
            "source": "vader_backend",
            "number_of_comments": len(comments),
            "number_updated": update_count,
            "timing": timings
        }
    except Exception as e:
        import traceback
        print("❌ Uncaught exception in /analyze:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
