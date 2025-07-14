#!/usr/bin/env python3
"""
get_trending_reels_insights.py

Fetch "view_count", "like_count" and "comments_count" for recent public Reels
under specified trending hashtags via the Instagram Graph API.

Usage:
  $ export IG_ACCESS_TOKEN="EAAX..."
  $ export IG_BUSINESS_USER_ID="1784140XXXXXX"
  $ python get_trending_reels_insights.py --hashtag DidYouKnow MindBlown ScienceFact
"""

import os
import sys
import csv
import time
import argparse
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────

ACCESS_TOKEN     = os.getenv("IG_ACCESS_TOKEN")
BUSINESS_USER_ID = os.getenv("IG_BUSINESS_USER_ID")

MEDIA_LIMIT      = 25
OUTPUT_CSV       = "trending_reels_insights.csv"
API_VERSION      = "v17.0"
BASE_URL         = f"https://graph.facebook.com/{API_VERSION}"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def api_get(path, params=None):
    params = params or {}
    params["access_token"] = ACCESS_TOKEN
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        print(f"[ERROR] GET {url} → {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()

def get_hashtag_id(tag: str) -> str:
    data = api_get(
        path="ig_hashtag_search",
        params={"user_id": BUSINESS_USER_ID, "q": tag}
    )
    items = data.get("data", [])
    if not items:
        print(f"[WARN] No hashtag ID found for #{tag}", file=sys.stderr)
        return None
    return items[0]["id"]

def get_recent_media_ids(hashtag_id: str, limit:int=MEDIA_LIMIT) -> list:
    data = api_get(
        path=f"{hashtag_id}/recent_media",
        params={
            "user_id": BUSINESS_USER_ID,
            "fields": "id,permalink,media_type",
            "limit": limit
        }
    )
    return [
        { "id": item["id"], "permalink": item["permalink"] }
        for item in data.get("data", [])
        if item.get("media_type") == "VIDEO"
    ]

def get_media_insights(media_id: str) -> dict:
    data = api_get(
        path=media_id,
        params={"fields": "like_count,comments_count,insights.metric(video_views)"}
    )
    insights = data.get("insights", {}).get("data", [])
    video_views = next((m["values"][0]["value"]
                        for m in insights
                        if m["name"] == "video_views"), None)
    return {
        "view_count": video_views,
        "like_count": data.get("like_count"),
        "comments_count": data.get("comments_count")
    }

# ─── MAIN FLOW ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch IG Reel insights for one or more hashtags"
    )
    parser.add_argument(
        "--hashtag", "-t",
        nargs="+",
        required=True,
        help="One or more hashtags (without #) to query"
    )
    args = parser.parse_args()

    if not ACCESS_TOKEN or not BUSINESS_USER_ID:
        print("❌ Please set IG_ACCESS_TOKEN and IG_BUSINESS_USER_ID in your environment.", file=sys.stderr)
        sys.exit(1)

    with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            "hashtag", "media_id", "permalink",
            "view_count", "like_count", "comments_count"
        ])
        writer.writeheader()

        for tag in args.hashtag:
            print(f"\n🔍 Searching #{tag} …")
            hashtag_id = get_hashtag_id(tag)
            if not hashtag_id:
                continue

            media_list = get_recent_media_ids(hashtag_id)
            print(f"  ▶ Found {len(media_list)} VIDEO items under #{tag}")

            for m in media_list:
                media_id  = m["id"]
                permalink = m["permalink"]
                print(f"    • Media {media_id} → fetching insights…", end="", flush=True)

                insights = get_media_insights(media_id)
                print(f" done: 👀{insights['view_count']} 👍{insights['like_count']} 💬{insights['comments_count']}")

                writer.writerow({
                    "hashtag": tag,
                    "media_id": media_id,
                    "permalink": permalink,
                    **insights
                })

                time.sleep(0.5)

    print(f"\n✅ Done! Results written to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()