#!/bin/bash

# run_wellness_finder.sh
# Convenient script to run the trending wellness reels finder

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MAX_REELS=20
OUTPUT_FORMAT="links"
OUTPUT_FILE="trending_wellness_links.txt"
MIN_VIEWS=10000
MIN_LIKES=500
MIN_COMMENTS=50

# Function to display usage
usage() {
    echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
    echo ""
    echo "Options:"
    echo "  -n, --max-reels NUMBER    Maximum number of reels to find (default: 20)"
    echo "  -o, --output FILE         Output file path (default: trending_wellness_links.txt)"
    echo "  -f, --format FORMAT       Output format: links, csv, json (default: links)"
    echo "  --min-views NUMBER        Minimum view count (default: 10000)"
    echo "  --min-likes NUMBER        Minimum like count (default: 500)"
    echo "  --min-comments NUMBER     Minimum comment count (default: 50)"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Environment Variables Required:"
    echo "  IG_ACCESS_TOKEN          Instagram Graph API access token"
    echo "  IG_BUSINESS_USER_ID      Instagram business user ID"
    echo "  OPENAI_API_KEY           OpenAI API key (optional but recommended)"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Find 20 reels, save links only"
    echo "  $0 -n 50 -f csv                           # Find 50 reels, save detailed CSV"
    echo "  $0 --min-views 50000 --min-likes 1000     # Higher engagement thresholds"
}

# Function to check environment variables
check_env() {
    echo -e "${BLUE}🔍 Checking environment variables...${NC}"
    
    if [ -z "$IG_ACCESS_TOKEN" ]; then
        echo -e "${RED}❌ IG_ACCESS_TOKEN is not set${NC}"
        echo "Get your Instagram Graph API token from: https://developers.facebook.com/tools/explorer/"
        exit 1
    fi
    
    if [ -z "$IG_BUSINESS_USER_ID" ]; then
        echo -e "${RED}❌ IG_BUSINESS_USER_ID is not set${NC}"
        echo "Get your business user ID from the Instagram Graph API"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  OPENAI_API_KEY is not set. AI content analysis will be limited.${NC}"
        echo "Get your OpenAI API key from: https://platform.openai.com/api-keys"
    else
        echo -e "${GREEN}✅ OpenAI API key found${NC}"
    fi
    
    echo -e "${GREEN}✅ Environment check complete${NC}"
}

# Function to check Python dependencies
check_dependencies() {
    echo -e "${BLUE}📦 Checking Python dependencies...${NC}"
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check required Python packages
    python3 -c "
import sys
required_packages = ['requests', 'openai']
missing_packages = []

for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print('❌ Missing Python packages:', ', '.join(missing_packages))
    print('Install with: pip install', ' '.join(missing_packages))
    sys.exit(1)
else:
    print('✅ All required Python packages are installed')
" || exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--max-reels)
            MAX_REELS="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        --min-views)
            MIN_VIEWS="$2"
            shift 2
            ;;
        --min-likes)
            MIN_LIKES="$2"
            shift 2
            ;;
        --min-comments)
            MIN_COMMENTS="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate format
if [[ ! "$OUTPUT_FORMAT" =~ ^(links|csv|json)$ ]]; then
    echo -e "${RED}❌ Invalid format: $OUTPUT_FORMAT. Must be: links, csv, or json${NC}"
    exit 1
fi

# Validate numeric arguments
if ! [[ "$MAX_REELS" =~ ^[0-9]+$ ]] || [ "$MAX_REELS" -lt 1 ]; then
    echo -e "${RED}❌ Invalid max-reels: $MAX_REELS. Must be a positive integer${NC}"
    exit 1
fi

if ! [[ "$MIN_VIEWS" =~ ^[0-9]+$ ]] || [ "$MIN_VIEWS" -lt 0 ]; then
    echo -e "${RED}❌ Invalid min-views: $MIN_VIEWS. Must be a non-negative integer${NC}"
    exit 1
fi

if ! [[ "$MIN_LIKES" =~ ^[0-9]+$ ]] || [ "$MIN_LIKES" -lt 0 ]; then
    echo -e "${RED}❌ Invalid min-likes: $MIN_LIKES. Must be a non-negative integer${NC}"
    exit 1
fi

if ! [[ "$MIN_COMMENTS" =~ ^[0-9]+$ ]] || [ "$MIN_COMMENTS" -lt 0 ]; then
    echo -e "${RED}❌ Invalid min-comments: $MIN_COMMENTS. Must be a non-negative integer${NC}"
    exit 1
fi

# Main execution
echo -e "${GREEN}🏃 Starting Trending Wellness Reels Finder${NC}"
echo -e "${BLUE}Configuration:${NC}"
echo "  Max reels: $MAX_REELS"
echo "  Output file: $OUTPUT_FILE"
echo "  Output format: $OUTPUT_FORMAT"
echo "  Min views: $MIN_VIEWS"
echo "  Min likes: $MIN_LIKES"
echo "  Min comments: $MIN_COMMENTS"
echo ""

# Run checks
check_env
check_dependencies

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/trending_wellness_reels_finder.py"

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}❌ Python script not found: $PYTHON_SCRIPT${NC}"
    exit 1
fi

# Run the Python script
echo -e "${BLUE}🚀 Running wellness reels finder...${NC}"
python3 "$PYTHON_SCRIPT" \
    --max-reels "$MAX_REELS" \
    --output "$OUTPUT_FILE" \
    --format "$OUTPUT_FORMAT" \
    --min-views "$MIN_VIEWS" \
    --min-likes "$MIN_LIKES" \
    --min-comments "$MIN_COMMENTS"

SCRIPT_EXIT_CODE=$?

if [ $SCRIPT_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Successfully completed! Results saved to: $OUTPUT_FILE${NC}"
    
    # Show additional output files if created
    if [ "$OUTPUT_FORMAT" = "csv" ]; then
        CSV_FILE="${OUTPUT_FILE%.txt}.csv"
        [ -f "$CSV_FILE" ] && echo -e "${GREEN}📊 Detailed CSV report: $CSV_FILE${NC}"
    elif [ "$OUTPUT_FORMAT" = "json" ]; then
        JSON_FILE="${OUTPUT_FILE%.txt}.json"
        [ -f "$JSON_FILE" ] && echo -e "${GREEN}📄 Full JSON report: $JSON_FILE${NC}"
    fi
    
    # Show preview of results
    if [ -f "$OUTPUT_FILE" ] && [ "$OUTPUT_FORMAT" = "links" ]; then
        LINK_COUNT=$(wc -l < "$OUTPUT_FILE")
        echo -e "${BLUE}📋 Found $LINK_COUNT trending wellness reels${NC}"
        echo -e "${BLUE}🔗 Preview of first 3 links:${NC}"
        head -3 "$OUTPUT_FILE" | nl
    fi
else
    echo -e "${RED}❌ Script failed with exit code: $SCRIPT_EXIT_CODE${NC}"
    exit $SCRIPT_EXIT_CODE
fi