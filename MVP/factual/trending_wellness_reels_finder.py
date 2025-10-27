#!/usr/bin/env python3
"""
trending_wellness_reels_finder.py

Advanced tool to find the top 20 trending reels daily that are factual in nature
and focused on wellness/health/biohacking/supplements/exercise/longevity.

This tool uses Instagram Graph API, OpenAI for content analysis, and sophisticated
filtering to identify high-quality factual content.

Usage:
  $ export IG_ACCESS_TOKEN="EAAX..."
  $ export IG_BUSINESS_USER_ID="1784140XXXXXX"
  $ export OPENAI_API_KEY="sk-..."
  $ python trending_wellness_reels_finder.py --max-reels 20 --output trending_wellness_links.txt
"""

import os
import sys
import csv
import time
import argparse
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import openai
from pathlib import Path

# ─── CONFIG ───────────────────────────────────────────────────────────────────

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
BUSINESS_USER_ID = os.getenv("IG_BUSINESS_USER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

API_VERSION = "v17.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Wellness-focused hashtags for search
WELLNESS_HASHTAGS = [
    "HealthTips", "Wellness", "Biohacking", "Longevity", "HealthyLiving",
    "Supplements", "FitnessScience", "NutritionalScience", "HealthFacts",
    "WellnessFacts", "HealthResearch", "BiohackingTips", "LongevityTips",
    "HealthOptimization", "NutritionalFacts", "SupplementScience",
    "FitnessMotivation", "HealthyLifestyle", "WellnessJourney",
    "HealthEducation", "PreventiveMedicine", "HolisticHealth",
    "MindBodyHealth", "HealthMyths", "ScienceBasedFitness",
    "EvidenceBasedNutrition", "HealthStudies", "WellnessResearch"
]

# Minimum engagement thresholds for trending content
MIN_VIEW_COUNT = 10000
MIN_LIKE_COUNT = 500
MIN_COMMENTS_COUNT = 50

# ─── OPENAI SETUP ─────────────────────────────────────────────────────────────

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def api_get(path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make a GET request to Instagram Graph API."""
    params = params or {}
    params["access_token"] = ACCESS_TOKEN
    url = f"{BASE_URL}/{path}"
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"[ERROR] GET {url} → {resp.status_code} {resp.text}", file=sys.stderr)
            return {}
        return resp.json()
    except requests.RequestException as e:
        print(f"[ERROR] Request failed: {e}", file=sys.stderr)
        return {}

def get_hashtag_id(tag: str) -> Optional[str]:
    """Get hashtag ID from hashtag name."""
    data = api_get(
        path="ig_hashtag_search",
        params={"user_id": BUSINESS_USER_ID, "q": tag}
    )
    items = data.get("data", [])
    if not items:
        print(f"[WARN] No hashtag ID found for #{tag}", file=sys.stderr)
        return None
    return items[0]["id"]

def get_recent_media_ids(hashtag_id: str, limit: int = 50) -> List[Dict[str, str]]:
    """Get recent media IDs from a hashtag."""
    data = api_get(
        path=f"{hashtag_id}/recent_media",
        params={
            "user_id": BUSINESS_USER_ID,
            "fields": "id,permalink,media_type,caption,timestamp",
            "limit": limit
        }
    )
    
    # Filter for videos (reels) only
    return [
        {
            "id": item["id"],
            "permalink": item["permalink"],
            "caption": item.get("caption", ""),
            "timestamp": item.get("timestamp", "")
        }
        for item in data.get("data", [])
        if item.get("media_type") == "VIDEO"
    ]

def get_media_insights(media_id: str) -> Dict[str, Any]:
    """Get engagement metrics for a media item."""
    data = api_get(
        path=media_id,
        params={"fields": "like_count,comments_count,insights.metric(video_views,reach,impressions)"}
    )
    
    insights = data.get("insights", {}).get("data", [])
    metrics = {}
    
    for insight in insights:
        metric_name = insight.get("name")
        if metric_name and insight.get("values"):
            metrics[metric_name] = insight["values"][0]["value"]
    
    return {
        "view_count": metrics.get("video_views", 0),
        "reach": metrics.get("reach", 0),
        "impressions": metrics.get("impressions", 0),
        "like_count": data.get("like_count", 0),
        "comments_count": data.get("comments_count", 0)
    }

def analyze_content_with_ai(caption: str, permalink: str) -> Dict[str, Any]:
    """Analyze content using OpenAI to determine if it's factual and wellness-related."""
    if not OPENAI_API_KEY:
        print("[WARN] OpenAI API key not provided, skipping AI analysis")
        return {"is_factual": False, "is_wellness": False, "confidence": 0}
    
    prompt = f"""
    Analyze this Instagram reel caption and determine:
    1. Is it primarily about wellness/health/biohacking/supplements/exercise/longevity?
    2. Does it contain factual claims (either scientifically true or false)?
    3. Rate the quality of factual content (1-10)
    4. Identify specific claims made
    
    Caption: "{caption}"
    URL: {permalink}
    
    Respond in JSON format:
    {{
        "is_wellness": boolean,
        "is_factual": boolean,
        "confidence": float (0-1),
        "quality_score": int (1-10),
        "wellness_categories": ["category1", "category2"],
        "factual_claims": ["claim1", "claim2"],
        "reasoning": "brief explanation"
    }}
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in health, wellness, and fact-checking. Analyze content for factual claims and wellness relevance."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"[ERROR] AI analysis failed: {e}", file=sys.stderr)
        return {"is_factual": False, "is_wellness": False, "confidence": 0}

def calculate_trending_score(insights: Dict[str, Any], ai_analysis: Dict[str, Any]) -> float:
    """Calculate a composite trending score based on engagement and AI analysis."""
    # Engagement score (normalized)
    view_score = min(insights.get("view_count", 0) / 100000, 1.0)  # Normalize to 100k views
    like_score = min(insights.get("like_count", 0) / 5000, 1.0)    # Normalize to 5k likes
    comment_score = min(insights.get("comments_count", 0) / 500, 1.0)  # Normalize to 500 comments
    
    engagement_score = (view_score * 0.5 + like_score * 0.3 + comment_score * 0.2)
    
    # AI quality score
    ai_score = (
        ai_analysis.get("confidence", 0) * 0.4 +
        (ai_analysis.get("quality_score", 0) / 10) * 0.6
    )
    
    # Bonus for factual wellness content
    content_bonus = 1.0
    if ai_analysis.get("is_wellness") and ai_analysis.get("is_factual"):
        content_bonus = 1.5
    elif ai_analysis.get("is_wellness") or ai_analysis.get("is_factual"):
        content_bonus = 1.2
    
    return engagement_score * ai_score * content_bonus

def meets_trending_criteria(insights: Dict[str, Any]) -> bool:
    """Check if content meets minimum trending criteria."""
    return (
        insights.get("view_count", 0) >= MIN_VIEW_COUNT and
        insights.get("like_count", 0) >= MIN_LIKE_COUNT and
        insights.get("comments_count", 0) >= MIN_COMMENTS_COUNT
    )

def find_trending_wellness_reels(max_reels: int = 20) -> List[Dict[str, Any]]:
    """Find trending wellness reels across multiple hashtags."""
    print(f"🔍 Searching for trending wellness reels across {len(WELLNESS_HASHTAGS)} hashtags...")
    
    all_reels = []
    
    for tag in WELLNESS_HASHTAGS:
        print(f"\n📊 Processing #{tag}...")
        hashtag_id = get_hashtag_id(tag)
        if not hashtag_id:
            continue
        
        media_list = get_recent_media_ids(hashtag_id, limit=25)
        print(f"  ▶ Found {len(media_list)} recent videos")
        
        for media in media_list:
            media_id = media["id"]
            permalink = media["permalink"]
            caption = media["caption"]
            
            print(f"    • Analyzing {media_id[:10]}...", end="", flush=True)
            
            # Get engagement metrics
            insights = get_media_insights(media_id)
            
            # Skip if doesn't meet basic trending criteria
            if not meets_trending_criteria(insights):
                print(" [skipped - low engagement]")
                continue
            
            # AI content analysis
            ai_analysis = analyze_content_with_ai(caption, permalink)
            
            # Skip if not wellness-related or factual
            if not (ai_analysis.get("is_wellness") and ai_analysis.get("is_factual")):
                print(" [skipped - not factual wellness content]")
                continue
            
            # Calculate trending score
            trending_score = calculate_trending_score(insights, ai_analysis)
            
            reel_data = {
                "hashtag": tag,
                "media_id": media_id,
                "permalink": permalink,
                "caption": caption[:200] + "..." if len(caption) > 200 else caption,
                "timestamp": media["timestamp"],
                "trending_score": trending_score,
                "insights": insights,
                "ai_analysis": ai_analysis
            }
            
            all_reels.append(reel_data)
            print(f" [score: {trending_score:.2f}]")
            
            time.sleep(0.5)  # Rate limiting
    
    # Sort by trending score and return top results
    all_reels.sort(key=lambda x: x["trending_score"], reverse=True)
    return all_reels[:max_reels]

def save_results(reels: List[Dict[str, Any]], output_file: str, format_type: str = "links"):
    """Save results to file in specified format."""
    if format_type == "links":
        # Save just the links for processing
        with open(output_file, "w", encoding="utf-8") as f:
            for reel in reels:
                f.write(f"{reel['permalink']}\n")
    
    elif format_type == "csv":
        # Save detailed CSV report
        csv_file = output_file.replace(".txt", ".csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "rank", "permalink", "hashtag", "trending_score",
                "view_count", "like_count", "comments_count",
                "confidence", "quality_score", "wellness_categories",
                "factual_claims", "caption_preview"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i, reel in enumerate(reels, 1):
                writer.writerow({
                    "rank": i,
                    "permalink": reel["permalink"],
                    "hashtag": reel["hashtag"],
                    "trending_score": round(reel["trending_score"], 3),
                    "view_count": reel["insights"]["view_count"],
                    "like_count": reel["insights"]["like_count"],
                    "comments_count": reel["insights"]["comments_count"],
                    "confidence": reel["ai_analysis"].get("confidence", 0),
                    "quality_score": reel["ai_analysis"].get("quality_score", 0),
                    "wellness_categories": "; ".join(reel["ai_analysis"].get("wellness_categories", [])),
                    "factual_claims": "; ".join(reel["ai_analysis"].get("factual_claims", [])),
                    "caption_preview": reel["caption"]
                })
    
    elif format_type == "json":
        # Save full JSON report
        json_file = output_file.replace(".txt", ".json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total_found": len(reels),
                "reels": reels
            }, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(
        description="Find top trending factual wellness reels on Instagram"
    )
    parser.add_argument(
        "--max-reels", "-n",
        type=int,
        default=20,
        help="Maximum number of reels to find (default: 20)"
    )
    parser.add_argument(
        "--output", "-o",
        default="trending_wellness_links.txt",
        help="Output file path (default: trending_wellness_links.txt)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["links", "csv", "json"],
        default="links",
        help="Output format (default: links)"
    )
    parser.add_argument(
        "--min-views",
        type=int,
        default=MIN_VIEW_COUNT,
        help=f"Minimum view count threshold (default: {MIN_VIEW_COUNT})"
    )
    parser.add_argument(
        "--min-likes",
        type=int,
        default=MIN_LIKE_COUNT,
        help=f"Minimum like count threshold (default: {MIN_LIKE_COUNT})"
    )
    parser.add_argument(
        "--min-comments",
        type=int,
        default=MIN_COMMENTS_COUNT,
        help=f"Minimum comment count threshold (default: {MIN_COMMENTS_COUNT})"
    )
    
    args = parser.parse_args()
    
    # Update global thresholds
    global MIN_VIEW_COUNT, MIN_LIKE_COUNT, MIN_COMMENTS_COUNT
    MIN_VIEW_COUNT = args.min_views
    MIN_LIKE_COUNT = args.min_likes
    MIN_COMMENTS_COUNT = args.min_comments
    
    # Validate required environment variables
    if not ACCESS_TOKEN or not BUSINESS_USER_ID:
        print("❌ Please set IG_ACCESS_TOKEN and IG_BUSINESS_USER_ID in your environment.", file=sys.stderr)
        sys.exit(1)
    
    if not OPENAI_API_KEY:
        print("⚠️  OpenAI API key not set. Content analysis will be limited.", file=sys.stderr)
    
    print(f"🎯 Finding top {args.max_reels} trending factual wellness reels...")
    print(f"📊 Minimum thresholds: {MIN_VIEW_COUNT} views, {MIN_LIKE_COUNT} likes, {MIN_COMMENTS_COUNT} comments")
    
    # Find trending reels
    trending_reels = find_trending_wellness_reels(args.max_reels)
    
    if not trending_reels:
        print("\n❌ No trending wellness reels found matching criteria.")
        sys.exit(1)
    
    print(f"\n✅ Found {len(trending_reels)} high-quality factual wellness reels!")
    
    # Save results
    save_results(trending_reels, args.output, args.format)
    
    # Display summary
    print(f"\n📋 Results saved to: {args.output}")
    print("\n🏆 Top 5 Results:")
    for i, reel in enumerate(trending_reels[:5], 1):
        print(f"{i}. Score: {reel['trending_score']:.2f} | #{reel['hashtag']}")
        print(f"   Views: {reel['insights']['view_count']:,} | Likes: {reel['insights']['like_count']:,}")
        print(f"   {reel['permalink']}")
        print(f"   Preview: {reel['caption'][:100]}...")
        print()

if __name__ == "__main__":
    main()