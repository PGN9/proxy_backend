import asyncio
import asyncpraw
import httpx
import json
import time
from dotenv import load_dotenv
from datetime import datetime, timezone
import os

load_dotenv()
# Reddit API credentials
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Supabase REST API credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")  # Service role for writes
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}


# Subreddits to scrape
SUBREDDITS_TO_SCRAPE = ["health", "fitness", "chiropractic"]
COMMENTS_LIMIT_PER_SUBREDDIT = 5  # number of comments per subreddit

# Supabase Table Names
TABLE_SUBREDDITS = "subreddits"
TABLE_AUTHORS = "authors"
TABLE_POSTS = "posts"
TABLE_COMMENTS = "comments"

async def upsert(table, data, conflict_field):
    """Upsert a record into Supabase table"""
    async with httpx.AsyncClient() as client:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        params = {"on_conflict": conflict_field}
        #Upserting data into table
        response = await client.post(
            url, headers=HEADERS, params=params, data=json.dumps(data)
        )
        if response.status_code >= 400:
            print(f"❌ Failed to upsert into {table}: {response.status_code} - {response.text}")


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
            async for comment in subreddit.comments(limit=COMMENTS_LIMIT_PER_SUBREDDIT):
                #Processing comment
                count += 1
                
                submission = comment.submission
                await submission.load()

                # Upsert subreddit
                await upsert(TABLE_SUBREDDITS, {"name": subreddit_name}, "name")

                # Upsert authors
                if comment.author:
                    await upsert(TABLE_AUTHORS, {"username": str(comment.author)}, "username")
                if submission.author:
                    await upsert(TABLE_AUTHORS, {"username": str(submission.author)}, "username")

                # Upsert post
                post_data = {
                    "id": submission.id,
                    "subreddit": subreddit_name,
                    "author": str(submission.author) if submission.author else None,
                    "title": submission.title,
                    "selftext": submission.selftext,
                    "created_utc": datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "permalink": f"https://reddit.com{submission.permalink}"
                }
                await upsert(TABLE_POSTS, post_data, "id")

                # Upsert comment
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
                await upsert(TABLE_COMMENTS, comment_data, "id")
                #Finished processing a comment

            total_comments += count
            #Finished scraping a subreddit
    finally:
        # Always close Reddit session
        await reddit.close()

    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n🎉 Done! Total comments processed: {total_comments}")
    print(f"⏱️ Total time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(scrape_and_store())