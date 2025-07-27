from fastapi import FastAPI, HTTPException
from typing import List
from dotenv import load_dotenv
import httpx
import json
import os
import time
import asyncio

load_dotenv()


# === Configuration constants ===
class Config:
    MODEL_BACKEND_URL = "http://localhost:8001/predict"
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
    TEXTS_TABLE = "comments"

    FETCH_STEP = 1000  # batch size when fetching from Supabase
    PROCESS_LIMIT = 100  # max comments to process (for testing)
    MODEL_BATCH_SIZE = 10  # batch size to send to model backend

    RETRIES = 3  # number of retries for model backend calls
    RETRY_DELAY_INITIAL = 1  # initial retry delay (seconds)


app = FastAPI()

if not Config.SUPABASE_URL or not Config.SUPABASE_API_KEY:
    raise RuntimeError(
        "Missing Supabase credentials in environment variables.")

HEADERS = {
    "apikey": Config.SUPABASE_API_KEY,
    "Authorization": f"Bearer {Config.SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal"
}


async def batch_upsert(table, data_list, conflict_field):
    async with httpx.AsyncClient() as client:
        url = f"{Config.SUPABASE_URL}/rest/v1/{table}"
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


async def _fetch_comments():
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


async def _process_comments_with_model(comments: List[dict]):
    all_model_results = []
    max_retries = Config.RETRIES
    model_batch_size = Config.MODEL_BATCH_SIZE
    num_batches = (len(comments) + model_batch_size - 1) // model_batch_size

    for i in range(0, len(comments), model_batch_size):
        batch_comments = comments[i:i + model_batch_size]
        print(
            f"Processing batch {i // model_batch_size + 1}/{num_batches} with {len(batch_comments)} comments."
        )

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=600.0) as client:
                    async with client.stream("POST",
                                             Config.MODEL_BACKEND_URL,
                                             json={"comments": batch_comments
                                                   }) as response:
                        response.raise_for_status()

                        # Temporary list to hold batch results before upsert
                        batch_results = []

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            data = json.loads(line)

                            if data.get("type") == "result":
                                batch_results.append(data)
                            elif data.get("type") == "stats":
                                print(f"Received stats: {data}")
                            else:
                                print(f"Unknown stream line: {data}")

                        # After streaming done, upsert batch results immediately
                        # If emotion_scores is a list of JSON strings, convert to list of dicts
                        for res in all_model_results:
                            if "emotion_scores" in res and isinstance(
                                    res["emotion_scores"], list):
                                # Check if first element is stringified JSON, then parse all
                                if res["emotion_scores"] and isinstance(
                                        res["emotion_scores"][0], str):
                                    res["emotion_scores"] = [
                                        json.loads(s)
                                        for s in res["emotion_scores"]
                                    ]

                        if batch_results:
                            for res in batch_results:
                                if "type" in res:
                                    del res[
                                        "type"]  # Remove the field not in DB
                            success = await batch_upsert(
                                Config.TEXTS_TABLE, batch_results, "id")
                            if success:
                                print(
                                    f"✅ Upserted {len(batch_results)} results for batch {i // model_batch_size + 1}"
                                )
                            else:
                                print(
                                    f"❌ Failed upsert for batch {i // model_batch_size + 1}"
                                )

                        all_model_results.extend(batch_results)
                break  # Exit retry loop if success
            except httpx.HTTPStatusError as e:
                print(f"❌ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(Config.RETRY_DELAY_INITIAL *
                                        (2**attempt))
                else:
                    raise
            except httpx.RequestError as e:
                print(
                    f"❌ Attempt {attempt + 1} failed due to network error: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(Config.RETRY_DELAY_INITIAL *
                                        (2**attempt))
                else:
                    raise

    return all_model_results, num_batches


async def _upsert_results(all_model_results: List[dict]):
    fields = [
        "sentiment", "sentiment_score", "emotions", "emotion_scores", "topics",
        "clusters"
    ]

    update_data_list = [{
        "id": res["id"],
        **{
            field: res[field]
            for field in fields if field in res
        }
    } for res in all_model_results]

    success = await batch_upsert(Config.TEXTS_TABLE, update_data_list, "id")
    update_count = len(update_data_list) if success else 0
    return update_count


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
        comments_data = await _fetch_comments()
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

        # Apply PROCESS_LIMIT for testing
        if Config.PROCESS_LIMIT and len(comments) > Config.PROCESS_LIMIT:
            comments = comments[:Config.PROCESS_LIMIT]
            print(f"Limiting processing to {Config.PROCESS_LIMIT} comments.")

        # Step 2: send to backend model with retry logic and batching
        send_start = time.perf_counter()
        all_model_results, num_batches = await _process_comments_with_model(
            comments)
        send_end = time.perf_counter()

        timings["model_processing_time"] = send_end - send_start

        # Step 3: upsert
        update_start = time.perf_counter()
        update_count = await _upsert_results(all_model_results)
        update_end = time.perf_counter()
        timings["supabase_update_time"] = update_end - update_start

        overall_end = time.perf_counter()
        timings["total_time"] = overall_end - overall_start

        model_metrics = {"total_processed_comments": len(all_model_results)}

        return {
            "model_metrics": model_metrics,
            "number_of_comments": len(comments),
            "number_updated": update_count,
            "timing": timings,
            "batch_info": {
                "batch_size": Config.MODEL_BATCH_SIZE,
                "number_of_batches": num_batches
            }
        }

    except Exception as e:
        import traceback
        print("❌ Uncaught exception in /analyze:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
