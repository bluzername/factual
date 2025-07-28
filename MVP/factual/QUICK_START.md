# Trending Wellness Reels Finder - Quick Start Guide

🎯 **Goal**: Find the top 20 trending reels daily that contain factual claims about wellness/health/biohacking/supplements/exercise/longevity.

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
cd MVP/factual
pip install -r requirements.txt
```

### 2. Setup Environment Variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env file with your API keys
nano .env
```

Required API keys:
- **Instagram Graph API**: `IG_ACCESS_TOKEN` and `IG_BUSINESS_USER_ID`
- **OpenAI API**: `OPENAI_API_KEY` (recommended for content analysis)

### 3. Run the Tool

**Option A: Simple Shell Script**
```bash
# Find 20 trending wellness reels (default)
./run_wellness_finder.sh

# Find 50 reels with detailed CSV output
./run_wellness_finder.sh -n 50 -f csv

# Higher engagement thresholds
./run_wellness_finder.sh --min-views 50000 --min-likes 1000
```

**Option B: Direct Python Script**
```bash
# Basic usage
python3 trending_wellness_reels_finder.py

# Custom parameters
python3 trending_wellness_reels_finder.py \
    --max-reels 20 \
    --output trending_wellness_links.txt \
    --format links \
    --min-views 10000
```

**Option C: MCP Server (API Interface)**
```bash
# Start the MCP server
python3 wellness_reels_mcp_server.py --port 8080

# Use the API
curl -X POST http://localhost:8080/tools/find_trending_wellness_reels \
  -H "Content-Type: application/json" \
  -d '{"max_reels": 20, "format": "links"}'
```

## 📋 Output

The tool generates a list of 20 Instagram reel URLs:
```
trending_wellness_links.txt
```

Example content:
```
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/reel/DEF456/
https://www.instagram.com/reel/GHI789/
...
```

## 🔧 Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `max_reels` | Number of reels to find | 20 |
| `format` | Output format (links/csv/json) | links |
| `min_views` | Minimum view count | 10,000 |
| `min_likes` | Minimum like count | 500 |
| `min_comments` | Minimum comment count | 50 |

## 🔄 Daily Automation

### Setup Daily Scheduler
```bash
# Run once and setup daily schedule
python3 schedule_daily_wellness_finder.py

# Run as daemon (keeps running)
python3 schedule_daily_wellness_finder.py --daemon

# Run once immediately
python3 schedule_daily_wellness_finder.py --run-once
```

### Cron Setup (Alternative)
```bash
# Add to crontab for daily execution at 6 PM
0 18 * * * cd /path/to/MVP/factual && ./run_wellness_finder.sh
```

## 🎯 How It Works

1. **Hashtag Search**: Searches 28 wellness hashtags like #HealthTips, #Biohacking, #Longevity
2. **Engagement Filter**: Filters by view count, likes, and comments
3. **AI Analysis**: Uses GPT-4 to identify factual health claims
4. **Trending Score**: Combines engagement metrics with content quality
5. **Top Results**: Returns the highest-scoring factual wellness reels

## 🛠️ Troubleshooting

**"IG_ACCESS_TOKEN is not set"**
- Get your token from [Facebook Graph API Explorer](https://developers.facebook.com/tools/explorer/)
- Ensure you have a Business Instagram account

**"No trending wellness reels found"**
- Lower engagement thresholds: `--min-views 5000 --min-likes 200`
- Try running at different times (6-9 PM is best)

**"AI analysis failed"**
- Check your OpenAI API key
- Ensure GPT-4 access (tool works with reduced functionality without OpenAI)

## 📊 Output Formats

### Links Format (Default)
```
trending_wellness_links.txt
```
Simple list of URLs for processing later.

### CSV Format
```bash
./run_wellness_finder.sh -f csv
```
Detailed spreadsheet with engagement metrics, AI scores, and factual claims.

### JSON Format
```bash
./run_wellness_finder.sh -f json
```
Complete data with full AI analysis and metadata.

## 🔗 API Usage

Start the MCP server and use these endpoints:

```bash
# Server info
GET http://localhost:8080/

# Health check
GET http://localhost:8080/health

# List tools
GET http://localhost:8080/tools

# Find trending reels
POST http://localhost:8080/tools/find_trending_wellness_reels
Content-Type: application/json

{
  "max_reels": 20,
  "format": "links",
  "min_views": 10000,
  "min_likes": 500,
  "min_comments": 50
}
```

## 🎁 Advanced Features

- **Archive Management**: Automatically archives daily results
- **Trending Score Algorithm**: Sophisticated ranking based on engagement + AI quality
- **Rate Limiting**: Respects Instagram API limits
- **Error Recovery**: Graceful handling of API failures
- **Notifications**: Optional webhook support for completion alerts

## 📈 Next Steps

1. **Process the Links**: Use the generated list with your existing factual pipeline
2. **Schedule Daily Runs**: Set up automation for daily content discovery
3. **Customize Hashtags**: Modify the hashtag list for specific focus areas
4. **Integrate with Factual**: Use the URLs with the existing video processing pipeline

---

**Need help?** Check the [full documentation](WELLNESS_REELS_FINDER.md) or the troubleshooting section above.

**Ready to scale?** Use the MCP server for API access and integrate with other tools.