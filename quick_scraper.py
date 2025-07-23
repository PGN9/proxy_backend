import os
import asyncio
import time
import psutil
import csv
from datetime import datetime
from dotenv import load_dotenv
import asyncpraw

load_dotenv()

POST_LIMIT = 1000
REDDIT_API_LIMIT = 950  # approx limit to avoid rate limiting
REPLACE_MORE_LIMIT = None  # None means fully expand "more comments"

global_api_call_count = 0
reddit_call_count = 0
reddit_window_start = time.time()

def bytes_to_mb(bytes_val):
    """Convert bytes to megabytes"""
    return bytes_val / (1024 * 1024)

def format_time(seconds):
    """Format seconds into readable time string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.1f}s"

def utc_to_iso(utc_ts):
    return datetime.utcfromtimestamp(utc_ts).isoformat()

async def async_guard_reddit(calls=1):
    global reddit_call_count, reddit_window_start, global_api_call_count
    now = time.time()
    elapsed = now - reddit_window_start
    if elapsed >= 60:
        reddit_window_start = now
        reddit_call_count = 0
        elapsed = 0
    if reddit_call_count + calls > REDDIT_API_LIMIT:
        sleep_time = 60 - elapsed
        print(f"Rate limit reached. Sleeping {sleep_time:.1f}s...", flush=True)
        await asyncio.sleep(sleep_time)
        reddit_window_start = time.time()
        reddit_call_count = 0
    
    global_api_call_count += calls

async def scrape_comments():
    global reddit_call_count, global_api_call_count
    comments = []
    posts_processed = 0
    total_comments_collected = 0
    
    # Get process for memory monitoring
    proc = psutil.Process()
    mem_before = proc.memory_info().rss
    start_time = time.time()

    # Create reddit instance inside the async function
    async with asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        requestor_kwargs={'timeout': 30}  # Add explicit timeout
    ) as reddit:
        
        print(f"Fetching top {POST_LIMIT} hot posts from r/gout...", flush=True)
        subreddit = await reddit.subreddit("AskReddit")
        reddit_call_count += 1
        global_api_call_count += 1

        async for submission in subreddit.hot(limit=POST_LIMIT):
            if reddit_call_count >= REDDIT_API_LIMIT:
                print("Reached Reddit API limit; stopping...", flush=True)
                break

            posts_processed += 1
            print(f"Processing post {posts_processed}/{POST_LIMIT}: {submission.id} - {submission.title}", flush=True)

            await async_guard_reddit()
            reddit_call_count += 1

            try:
                # Add timeout handling for comment fetching
                comments_task = asyncio.create_task(submission.comments())
                comments_obj = await asyncio.wait_for(comments_task, timeout=30)
                
                replace_more_task = asyncio.create_task(comments_obj.replace_more(limit=REPLACE_MORE_LIMIT))
                await asyncio.wait_for(replace_more_task, timeout=60)
                
                comment_list = comments_obj.list()
            except asyncio.TimeoutError:
                print(f"Timeout fetching comments for {submission.id}; skipping...", flush=True)
                continue
            except Exception as e:
                print(f"Error fetching comments for {submission.id}: {e}", flush=True)
                continue

            for comment in comment_list:
                if reddit_call_count >= REDDIT_API_LIMIT:
                    print("Reached Reddit API limit during comment fetching; stopping...", flush=True)
                    break
                
                # Clean the comment body for CSV (remove newlines and quotes)
                clean_body = comment.body.replace('\n', ' ').replace('\r', ' ').replace('"', '""')
                
                comments.append({
                    "post_id": submission.id,
                    "comment_id": comment.id,
                    "created_utc": utc_to_iso(comment.created_utc),
                    "body": clean_body,
                    "score": comment.score,
                    "is_deleted": comment.author is None
                })

            total_comments_collected += len(comment_list)
            print(f"Collected {len(comment_list)} comments from post {submission.id} (Total: {total_comments_collected})", flush=True)

    # Calculate final metrics
    end_time = time.time()
    elapsed = end_time - start_time
    mem_after = proc.memory_info().rss
    
    # Save comments to CSV
    csv_filename = f"reddit_gout_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['post_id', 'comment_id', 'created_utc', 'body', 'score', 'is_deleted']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for comment in comments:
            writer.writerow(comment)
    
    print(f"\n--- Scraping Summary ---")
    print(f"📄 Posts processed: {posts_processed}")
    print(f"💬 Total comments collected: {total_comments_collected}")
    print(f"💾 Comments saved to: {csv_filename}")
    print(f"⏱️ Total scraping time: {format_time(elapsed)}")
    if posts_processed > 0:
        avg_time_per_post = elapsed / posts_processed
        print(f"📊 Average time per post: {avg_time_per_post:.2f}s")
    
    print(f"\n--- API Call and Resource Usage ---")
    print(f"🔄 Total Reddit API calls made: {global_api_call_count}")
    print(f"⏱ Raw time elapsed: {elapsed:.2f}s")
    print(f"🖥️ Memory before: {bytes_to_mb(mem_before):.1f} MB")
    print(f"🖥️ Memory after : {bytes_to_mb(mem_after):.1f} MB")
    print(f"🖥️ Peak usage   : {bytes_to_mb(mem_after - mem_before):.1f} MB")

    return comments

async def main():
    try:
        all_comments = await scrape_comments()
        print(f"Total comments scraped: {len(all_comments)}", flush=True)
        return all_comments
    except Exception as e:
        print(f"Error in main: {e}", flush=True)
        return []

if __name__ == "__main__":
    # Ensure we're using the correct event loop policy on Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
