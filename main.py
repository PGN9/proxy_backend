from fastapi import FastAPI, HTTPException
from typing import List
from dotenv import load_dotenv
import httpx
import json
import os
import time
import psutil
import logging
import asyncio

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

load_dotenv()

app = FastAPI()
MODEL_BACKEND_URL = os.getenv("MODEL_BACKEND_URL", "http://127.0.0.1:8601/predict")


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

TEXTS_TABLE = "Vader_Backend"

MODEL_BATCH_SIZE = 100
PROCESS_LIMIT = None  # or 0, and change the check accordingly
  # Or whatever upper limit you want



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
    # Supabase's default limit is 1000, so fetching 1000 at a time is efficient.
    # We'll use 'limit' and 'offset' query parameters for simpler pagination.
    limit = 1000
    offset = 0

    async with httpx.AsyncClient( ) as client:
        while True:
            # Use 'limit' and 'offset' query parameters instead of 'Range' header
            url = f"{SUPABASE_URL}/rest/v1/{TEXTS_TABLE}?select=id,body&limit={limit}&offset={offset}"
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status() # Raise an exception for HTTP errors
            batch = response.json()

            print(f"Fetched {len(batch)} comments from Supabase (offset: {offset}): {batch[:2]}")

            if not batch: # If the batch is empty, we've fetched all comments
                break

            all_comments.extend(batch)
            offset += len(batch) # Increment offset by the number of comments actually fetched

    return all_comments


@app.get("/")
def root():
    return {"message": "proxy backend is running."}


@app.get("/analyze")
async def analyze_sentiment():
    try:
        timings = {}
        overall_start = time.perf_counter()

        # Step 1: Fetch comments from Supabase
        fetch_start = time.perf_counter()
        comments_data = await fetch_all_comments()
        fetch_end = time.perf_counter()
        timings["supabase_fetch_time"] = fetch_end - fetch_start

        # Filter to ensure valid data
        comments = [
            {"id": item["id"], "body": item["body"]}
            for item in comments_data if "id" in item and "body" in item
        ]

        print(f"🧪 Number of comments to process: {len(comments)}")
        if not comments:
            return {"message": "No comments found in Supabase."}

        # Apply PROCESS_LIMIT if set
        #if PROCESS_LIMIT and PROCESS_LIMIT > 0 and len(comments) > PROCESS_LIMIT:
            #comments = comments[:PROCESS_LIMIT]
            #print(f"Limiting to {PROCESS_LIMIT} comments.")

        # Step 2: Call model backend in batches
        send_start = time.perf_counter()
        all_results = []
        stats_data = {}
        async with httpx.AsyncClient(timeout=600.0) as client:
            for i in range(0, len(comments), MODEL_BATCH_SIZE):
                batch = comments[i:i + MODEL_BATCH_SIZE]
                print(f"🔁 Sending batch {i // MODEL_BATCH_SIZE + 1}")
                batch_send_start = time.perf_counter()
                resp = await client.post(MODEL_BACKEND_URL, json={"comments": batch})
                batch_send_end = time.perf_counter()
                
                resp.raise_for_status()
                data = resp.json()
                model_time = data.get("model_processing_time", 0)
                send_time = batch_send_end - batch_send_start - model_time if model_time else batch_send_end - batch_send_start

                timings.setdefault("model_send_time", 0)
                timings["model_send_time"] += send_time
                

                # Pull out batch results
                batch_results = data.get("results", [])
                all_results.extend(batch_results)

                # Collect/merge any top-level stats
                if not stats_data:
                    stats_data = {k: v for k, v in data.items() if k != "results"}
                else:
    # Use min for initial, max for peak, sum for sizes
                    stats_data["memory_initial_mb"] = min(
                        stats_data.get("memory_initial_mb", data["memory_initial_mb"]),
                        data.get("memory_initial_mb", stats_data.get("memory_initial_mb", 0))
                    )
                    stats_data["memory_peak_mb"] = max(
                        stats_data.get("memory_peak_mb", 0),
                        data.get("memory_peak_mb", 0)
                    )
                    stats_data["total_data_size_kb"] = round(
                        stats_data.get("total_data_size_kb", 0) + data.get("total_data_size_kb", 0), 2
                    )
                    stats_data["total_return_size_kb"] = round(
                        stats_data.get("total_return_size_kb", 0) + data.get("total_return_size_kb", 0), 2
                    )

        send_end = time.perf_counter()
        timings["model_processing_time"] = send_end - send_start
        timings["model_send_time"] = round(timings.get("model_send_time", 0), 3)
        # Step 3: Upsert back to Supabase
        update_start = time.perf_counter()
        update_data_list = [
    {
        "id": res["id"],
        "sentiment": res.get("sentiment"),
        "sentiment_score": res.get("sentiment_score"),
        "body": res.get("body")  # optional if needed for display only
    }
    for res in all_results
]

        success = await batch_upsert(TEXTS_TABLE, update_data_list, "id")
        update_count = len(update_data_list) if success else 0
        update_end = time.perf_counter()
        timings["supabase_update_time"] = update_end - update_start

        overall_end = time.perf_counter()
        timings["total_time"] = overall_end - overall_start

        return {
    "model_metrics": {
        "total_processed_comments": len(all_results),
        **stats_data
    },
    "number_of_comments": len(comments),
    "number_updated": update_count,
    "timing": timings,
    "batch_info": {
        "batch_size": MODEL_BATCH_SIZE,
        "number_of_batches": (len(comments) + MODEL_BATCH_SIZE - 1) // MODEL_BATCH_SIZE
    },
    "results_preview": update_data_list[:5]  # preview top 5
}

    except Exception as e:
        import traceback
        print("❌ Uncaught exception in /analyze:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    
process = psutil.Process(os.getpid())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(log_memory_usage())

async def log_memory_usage():
    while True:
        mem_mb = process.memory_info().rss / (1024 * 1024)
        logger.info(f"[MEMORY MONITOR] Proxy memory usage: {mem_mb:.2f} MB")
        await asyncio.sleep(10)

@app.get("/debug")
def debug():
    return {
        "MODEL_BACKEND_URL": MODEL_BACKEND_URL,
        "SUPABASE_URL": SUPABASE_URL,
        "TEXTS_TABLE": TEXTS_TABLE,
    }
