# Trending Wellness Reels Finder

An advanced tool to discover the top 20 trending Instagram reels daily that contain factual claims and focus on wellness, health, biohacking, supplements, exercise, and longevity topics.

## 🎯 Overview

This tool combines the Instagram Graph API with OpenAI's GPT-4 to:

1. **Search** across 28 wellness-focused hashtags
2. **Filter** content by engagement metrics (views, likes, comments)
3. **Analyze** captions using AI to identify factual claims
4. **Score** content based on trending potential and content quality
5. **Generate** a curated list of 20 top-performing factual wellness reels

## 🚀 Features

- **Comprehensive Hashtag Coverage**: Searches 28 wellness/health hashtags
- **AI-Powered Content Analysis**: Uses GPT-4 to identify factual claims
- **Smart Filtering**: Filters by engagement thresholds and content quality
- **Multiple Output Formats**: Links, CSV, or JSON with detailed analytics
- **Trending Score Algorithm**: Combines engagement metrics with AI quality scores
- **Rate Limiting**: Respects API limits with built-in delays
- **Robust Error Handling**: Graceful failure recovery

## 📋 Requirements

### API Access Required

1. **Instagram Graph API**:
   - Business Instagram account
   - Facebook App with Instagram Graph API access
   - Access token (`IG_ACCESS_TOKEN`)
   - Business user ID (`IG_BUSINESS_USER_ID`)

2. **OpenAI API** (recommended):
   - OpenAI account
   - API key (`OPENAI_API_KEY`)
   - GPT-4 access

### Python Dependencies

```bash
pip install requests openai python-dotenv
```

## ⚙️ Setup

### 1. Get Instagram Graph API Access

1. Create a Facebook App at [Facebook Developers](https://developers.facebook.com/)
2. Add Instagram Graph API to your app
3. Connect your Instagram Business account
4. Generate an access token using the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
5. Get your Instagram Business User ID

### 2. Get OpenAI API Access

1. Sign up at [OpenAI Platform](https://platform.openai.com/)
2. Generate an API key
3. Ensure you have GPT-4 access

### 3. Set Environment Variables

Create a `.env` file or export variables:

```bash
export IG_ACCESS_TOKEN="your_instagram_access_token"
export IG_BUSINESS_USER_ID="your_business_user_id"
export OPENAI_API_KEY="your_openai_api_key"
```

## 🎬 Usage

### Quick Start

```bash
# Basic usage - find 20 reels, save links
./run_wellness_finder.sh

# Find 50 reels with detailed CSV output
./run_wellness_finder.sh -n 50 -f csv

# Higher engagement thresholds
./run_wellness_finder.sh --min-views 50000 --min-likes 1000
```

### Python Script Direct Usage

```bash
# Basic usage
python3 trending_wellness_reels_finder.py

# Custom parameters
python3 trending_wellness_reels_finder.py \
    --max-reels 30 \
    --output my_wellness_reels.txt \
    --format json \
    --min-views 25000 \
    --min-likes 1000 \
    --min-comments 100
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --max-reels` | Maximum number of reels to find | 20 |
| `-o, --output` | Output file path | `trending_wellness_links.txt` |
| `-f, --format` | Output format: links, csv, json | `links` |
| `--min-views` | Minimum view count threshold | 10,000 |
| `--min-likes` | Minimum like count threshold | 500 |
| `--min-comments` | Minimum comment count threshold | 50 |

## 📊 How It Works

### 1. Hashtag Search

The tool searches across these wellness-focused hashtags:

**Core Health**: `HealthTips`, `Wellness`, `HealthyLiving`, `HealthFacts`, `HealthEducation`

**Specialized Areas**: `Biohacking`, `Longevity`, `Supplements`, `FitnessScience`, `NutritionalScience`

**Evidence-Based**: `HealthResearch`, `ScienceBasedFitness`, `EvidenceBasedNutrition`, `HealthStudies`

**Wellness Journey**: `WellnessJourney`, `HealthOptimization`, `PreventiveMedicine`, `HolisticHealth`

### 2. Content Filtering

**Engagement Thresholds**:
- Minimum 10,000 views
- Minimum 500 likes  
- Minimum 50 comments

**Content Analysis** (via GPT-4):
- Must be wellness/health related
- Must contain factual claims (true or false)
- Quality score assessment (1-10)
- Identification of specific claims

### 3. Trending Score Algorithm

```python
trending_score = engagement_score * ai_quality_score * content_bonus

# Where:
# engagement_score = weighted combination of views, likes, comments
# ai_quality_score = confidence + quality_score from GPT-4
# content_bonus = 1.5x for factual wellness, 1.2x for wellness or factual
```

### 4. Output Generation

**Links Format** (`trending_wellness_links.txt`):
```
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/reel/DEF456/
...
```

**CSV Format** includes:
- Rank, permalink, hashtag, trending score
- Engagement metrics (views, likes, comments)
- AI analysis (confidence, quality score)
- Wellness categories and factual claims
- Caption preview

**JSON Format** includes complete data with full AI analysis.

## 📁 Output Files

### Links Output
```
trending_wellness_links.txt     # List of Instagram reel URLs
```

### CSV Output
```
trending_wellness_links.csv     # Detailed spreadsheet with analytics
```

### JSON Output
```
trending_wellness_links.json    # Complete data with metadata
```

## 🔧 Configuration

### Wellness Hashtags

You can modify the `WELLNESS_HASHTAGS` list in the Python script to focus on specific areas:

```python
WELLNESS_HASHTAGS = [
    "HealthTips", "Wellness", "Biohacking", "Longevity",
    # Add your custom hashtags here
]
```

### Engagement Thresholds

Adjust minimum engagement requirements:

```python
MIN_VIEW_COUNT = 10000      # Minimum views
MIN_LIKE_COUNT = 500        # Minimum likes  
MIN_COMMENTS_COUNT = 50     # Minimum comments
```

### AI Analysis Prompt

Customize the OpenAI analysis prompt in the `analyze_content_with_ai()` function for different content evaluation criteria.

## 🛠️ Troubleshooting

### Common Issues

**"IG_ACCESS_TOKEN is not set"**
- Set your Instagram Graph API access token
- Ensure token has not expired (tokens expire after 60 days by default)

**"No hashtag ID found"**
- Hashtag may not exist or have restricted access
- Try using more popular hashtag variations

**"AI analysis failed"**
- Check OpenAI API key is valid
- Ensure you have GPT-4 access
- Check API rate limits

**"No trending wellness reels found"**
- Lower engagement thresholds with `--min-views`, `--min-likes`, `--min-comments`
- Try running at different times of day
- Expand hashtag list

### Debug Mode

Add debug output by modifying the script:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Best Practices

### Daily Usage
- Run during peak Instagram hours (6-9 PM local time)
- Use consistent engagement thresholds for comparative analysis
- Archive results with timestamps for trend analysis

### Content Quality
- Review AI analysis results manually for accuracy
- Adjust quality score thresholds based on your standards
- Consider additional manual verification for high-stakes content

### API Management
- Monitor Instagram Graph API rate limits
- Rotate access tokens before expiration
- Cache results to avoid redundant API calls

## 🔍 Example Outputs

### Console Output
```
🔍 Searching for trending wellness reels across 28 hashtags...

📊 Processing #HealthTips...
  ▶ Found 25 recent videos
    • Analyzing 1784140xxx... [score: 0.85]
    • Analyzing 1784141xxx... [skipped - low engagement]
    • Analyzing 1784142xxx... [score: 0.92]

✅ Found 20 high-quality factual wellness reels!

🏆 Top 5 Results:
1. Score: 0.92 | #Biohacking
   Views: 156,789 | Likes: 8,234
   https://www.instagram.com/reel/ABC123/
   Preview: New study shows cold exposure increases brown fat by 15%...
```

### CSV Data Sample
```csv
rank,permalink,hashtag,trending_score,view_count,like_count,comments_count,confidence,quality_score,wellness_categories,factual_claims,caption_preview
1,https://www.instagram.com/reel/ABC123/,Biohacking,0.92,156789,8234,456,0.89,8,"biohacking; longevity","Cold exposure increases brown fat; Brown fat burns more calories",New study shows cold exposure...
```

## 📞 Support

For issues and questions:
- Check the [troubleshooting section](#troubleshooting)
- Review API documentation for Instagram Graph API and OpenAI
- Verify environment variables and API access

## 📄 License

This tool is part of the Factual project and follows the same MIT license terms.

---

**Happy wellness content discovery!** 🌿✨