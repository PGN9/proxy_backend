How to use:
...

How to use:
reddit_scraper.py

- specify which subreddits and number of comments in the python file.

- Install dependencies:

pip install -r requirements.txt

- Create tables in Supabase with this schema:

create table subreddits (
name text primary key
);

create table authors (
username text primary key
);

create table posts (
id text primary key,
subreddit text references subreddits(name),
author text references authors(username),
title text,
selftext text,
created_utc timestamptz,
score integer,
num_comments integer,
permalink text
);

create table comments (
id text primary key,
post_id text references posts(id),
subreddit text references subreddits(name),
author text references authors(username),
body text,
created_utc timestamptz,
score integer,
parent_id text,
permalink text,
sentiment text,
sentiment_score numeric,
readability numeric,
hashtag_count integer,
emotion text,
clusters text
);

- Create a .env file with your Reddit and Supabase credentials:

REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_API_KEY=your_service_role_key

- Run the script:

python main.py
