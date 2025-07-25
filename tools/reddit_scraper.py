import asyncio
import asyncpraw
import httpx
import json
import time
import logging
from dotenv import load_dotenv
from datetime import datetime, timezone
import os

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reddit API credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Supabase REST API credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

SUBREDDITS_TO_SCRAPE = ["health", "fitness"]
COMMENTS_LIMIT_PER_SUBREDDIT = 5000

TABLE_SUBREDDITS = "subreddits"
TABLE_AUTHORS = "authors"
TABLE_POSTS = "posts"
TABLE_COMMENTS = "comments"

BATCH_SIZE = 50  # How many records per batch upsert


async def upsert(table, data_list, conflict_field):
    if not data_list:
        return
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {"on_conflict": conflict_field}
        try:
            response = await client.post(
                url, headers=HEADERS, params=params, data=json.dumps(data_list)
            )
            response.raise_for_status()
            logger.info(f"Upserted batch of {len(data_list)} records into {table}.")
        except Exception as e:
            logger.error(f"Failed batch upsert into {table}: {e}")

async def scrape_and_store():
    reddit = asyncpraw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )

    total_comments = 0
    start_time = time.time()
    print("🚀 Starting Reddit scrape...")

    try:
        for subreddit_name in SUBREDDITS_TO_SCRAPE:
            print(f"\n🔍 Scraping r/{subreddit_name}")
            subreddit = await reddit.subreddit(subreddit_name)

            count = 0
            # We'll accumulate comments data here, to upsert after
            comments_to_upsert = []

            async for comment in subreddit.comments(limit=COMMENTS_LIMIT_PER_SUBREDDIT):
                count += 1
                
                submission = comment.submission
                await submission.load()

                # Upsert subreddit first
                await upsert(TABLE_SUBREDDITS, {"name": subreddit_name}, "name")

                # Upsert authors first
                if comment.author:
                    await upsert(TABLE_AUTHORS, {"username": str(comment.author)}, "username")
                if submission.author:
                    await upsert(TABLE_AUTHORS, {"username": str(submission.author)}, "username")

                # Upsert post next
                post_data = {
                    "id": submission.id,
                    "subreddit": subreddit_name,
                    "author": str(submission.author) if submission.author else None,
                    "title": submission.title,
                    "selftext": submission.selftext,
                    "created_utc": datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "permalink": f"https://reddit.com{submission.permalink}"
                }
                await upsert(TABLE_POSTS, post_data, "id")

                # Save comment data, but don't upsert yet
                comment_data = {
                    "id": comment.id,
                    "post_id": submission.id,
                    "subreddit": subreddit_name,
                    "author": str(comment.author) if comment.author else None,
                    "body": comment.body,
                    "created_utc": datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
                    "score": comment.score,
                    "parent_id": comment.parent_id,
                    "permalink": f"https://reddit.com{comment.permalink}",
                    "sentiment": None,
                    "sentiment_score": None,
                    "readability": None,
                    "hashtag_count": None,
                    "emotion": None,
                    "clusters": None
                }
                comments_to_upsert.append(comment_data)

            # After finishing this subreddit, upsert all comments at once
            for comment_data in comments_to_upsert:
                await upsert(TABLE_COMMENTS, comment_data, "id")

            total_comments += count

    finally:
        await reddit.close()

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n🎉 Done! Total comments processed: {total_comments}")
    print(f"⏱️ Total time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(scrape_and_store())
