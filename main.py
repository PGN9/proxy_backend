from fastapi import FastAPI, HTTPException
from typing import List
from dotenv import load_dotenv
import httpx
import json
import os
import time
import asyncio

load_dotenv()

app = FastAPI()


# === Configuration constants ===
class Config:
    MODEL_BACKEND_URL = "https://vader-backend-po5q.onrender.com/predict"
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
    TEXTS_TABLE = "comments"

    FETCH_STEP = 1000  # batch size when fetching from Supabase
    PROCESS_LIMIT = 10  # max comments to process (for testing)
    MODEL_BATCH_SIZE = 10  # batch size to send to model backend

    RETRIES = 3  # number of retries for model backend calls
    RETRY_DELAY_INITIAL = 1  # initial retry delay (seconds)


if not Config.SUPABASE_URL or not Config.SUPABASE_API_KEY:
    raise RuntimeError(
        "Missing Supabase credentials in environment variables.")

HEADERS = {
    "apikey": Config.SUPABASE_API_KEY,
    "Authorization": f"Bearer {Config.SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}


# === Helper functions ===
async def batch_upsert(table, data_list, conflict_field):
    async with httpx.AsyncClient() as client:
        url = f"{Config.SUPABASE_URL}/rest/v1/{table}"
        params = {"on_conflict": conflict_field}
        response = await client.post(url,
                                     headers=HEADERS,
                                     params=params,
                                     json=data_list)
        if response.status_code >= 400:
            print(
                f"❌ Failed batch upsert into {table}: {response.status_code} - {response.text}"
            )
            return False
        return True


async def fetch_all_comments():
    all_comments = []
    step = Config.FETCH_STEP
    offset = 0

    async with httpx.AsyncClient() as client:
        while True:
            headers = {**HEADERS, "Range": f"{offset}-{offset + step - 1}"}
            url = f"{Config.SUPABASE_URL}/rest/v1/{Config.TEXTS_TABLE}?select=id,body"
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


# === Routes ===


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.get("/analyze")
async def analyze_sentiment():
    try:
        timings = {}
        overall_start = time.perf_counter()

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Fetch comments from Supabase
            fetch_start = time.perf_counter()
            comments_data = await fetch_all_comments()
            fetch_end = time.perf_counter()
            timings["supabase_fetch_time"] = fetch_end - fetch_start

            comments = [{
                "id": item["id"],
                "body": item["body"]
            } for item in comments_data if "id" in item and "body" in item
                        ][:Config.PROCESS_LIMIT]

            print(f"🧪 Number of comments to process: {len(comments)}")
            if not comments:
                return {"message": "No comments found in Supabase."}

            # Send comments to model backend in batches with retry
            batch_size = Config.MODEL_BATCH_SIZE
            all_model_results = []
            send_start = time.perf_counter()

            for i in range(0, len(comments), batch_size):
                batch_comments = comments[i:i + batch_size]
                retries = Config.RETRIES
                delay = Config.RETRY_DELAY_INITIAL
                for attempt in range(retries):
                    try:
                        model_resp = await client.post(
                            Config.MODEL_BACKEND_URL,
                            json={"comments": batch_comments})
                        print("✅ Sent batch to backend, status:",
                              model_resp.status_code)
                        model_resp.raise_for_status()
                        results = model_resp.json().get("results", [])
                        all_model_results.extend(results)
                        break
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in {502, 503}:
                            print(
                                f"⚠️ Attempt {attempt + 1}/{retries}: "
                                f"{exc.response.status_code} error. Retrying in {delay}s..."
                            )
                            await asyncio.sleep(delay)
                            delay *= 2
                        else:
                            raise HTTPException(
                                status_code=exc.response.status_code,
                                detail=f"Backend error: {exc}",
                            )
                    except httpx.RequestError as exc:
                        print(
                            f"⚠️ Attempt {attempt + 1}/{retries}: Network error: {exc}. Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= 2
                else:
                    raise HTTPException(
                        status_code=504,
                        detail=
                        "Failed to process batch after multiple retries.",
                    )

            send_end = time.perf_counter()
            timings["model_send_time"] = send_end - send_start

            # Upsert results back to Supabase
            update_start = time.perf_counter()
            fields = [
                "sentiment",
                "sentiment_score",
                "emotions",
                "emotion_scores",
                "topics",
                "clusters",
            ]

            update_data_list = [{
                "id": res["id"],
                **{
                    field: res[field]
                    for field in fields if field in res
                },
            } for res in all_model_results]

            success = await batch_upsert(Config.TEXTS_TABLE, update_data_list,
                                         "id")
            update_count = len(update_data_list) if success else 0
            update_end = time.perf_counter()
            timings["supabase_update_time"] = update_end - update_start

            overall_end = time.perf_counter()
            timings["total_time"] = overall_end - overall_start

            # Rename and round timing values for final response
            timings["model_processing_time"] = timings.pop("model_send_time")
            timings = {k: round(v, 4) for k, v in timings.items()}

            model_metrics = {"model_used": "vader"}

            return {
                "model_metrics": model_metrics,
                "number_of_comments": len(comments),
                "number_updated": update_count,
                "timing": timings,
            }

    except HTTPException as http_exc:
        raise http_exc

    except Exception as e:
        import traceback

        print("❌ Uncaught exception in /analyze:")
        traceback.print_exc()
        raise HTTPException(status_code=500,
                            detail="Internal Server Error: " + str(e))
