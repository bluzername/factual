#!/bin/bash
# Enhanced wrapper script for the Factual pipeline v2.0
# Now supports unified processing with HTML summaries and engagement metrics

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Single URL mode:"
    echo "  $0 <instagram_reel_url> [config_file]"
    echo ""
    echo "Batch processing mode:"
    echo "  $0 --batch <batch_file> [config_file]"
    echo ""
    echo "Options:"
    echo "  --batch FILE    Process multiple URLs from a text file (one URL per line)"
    echo "  --unified       Use the new unified processor (default: true)"
    echo "  --legacy        Use the legacy pipeline processor"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 https://www.instagram.com/reel/ABC123/"
    echo "  $0 --batch urls.txt"
    echo "  $0 --batch urls.txt config.json"
    echo "  $0 --legacy --batch urls.txt  # Use legacy processor"
    echo ""
    echo "New Features in v2.0:"
    echo "  - HTML summaries with sources"
    echo "  - Instagram-ready descriptions"
    echo "  - Engagement metrics tracking"
    echo "  - Proper session isolation in batch mode"
    echo "  - Enhanced batch reporting"
    echo ""
    echo "Batch file format:"
    echo "  Each line should contain one Instagram/Facebook reel URL"
    echo "  Empty lines and lines starting with # are ignored"
}

# Check for help option
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_usage
    exit 0
fi

# Check if no arguments provided
if [ $# -lt 1 ]; then
    echo "Error: No arguments provided"
    echo ""
    show_usage
    exit 1
fi

# Initialize variables
USE_UNIFIED=true
MODE=""
URL=""
BATCH_FILE=""
CONFIG_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --batch)
            MODE="batch"
            shift
            if [ $# -lt 1 ]; then
                echo "Error: --batch requires a batch file argument"
                show_usage
                exit 1
            fi
            BATCH_FILE="$1"
            shift
            ;;
        --unified)
            USE_UNIFIED=true
            shift
            ;;
        --legacy)
            USE_UNIFIED=false
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        -*)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$MODE" ]; then
                # First non-option argument is URL in single mode
                MODE="single"
                URL="$1"
                shift
                # Next argument might be config file
                if [ $# -gt 0 ] && [[ ! "$1" =~ ^-- ]]; then
                    CONFIG_FILE="$1"
                    shift
                fi
            elif [ "$MODE" = "batch" ] && [ -z "$CONFIG_FILE" ]; then
                # This might be config file for batch mode
                CONFIG_FILE="$1"
                shift
            else
                echo "Error: Unexpected argument $1"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Validate arguments
if [ -z "$MODE" ]; then
    echo "Error: No URL or batch file provided"
    show_usage
    exit 1
fi

if [ "$MODE" = "batch" ]; then
    if [ ! -f "$BATCH_FILE" ]; then
        echo "Error: Batch file '$BATCH_FILE' not found"
        exit 1
    fi
    echo "Batch processing mode"
    echo "Batch file: $BATCH_FILE"
else
    echo "Single URL processing mode"
    echo "URL: $URL"
fi

if [ -n "$CONFIG_FILE" ]; then
    echo "Config file: $CONFIG_FILE"
fi

echo "Processor: $([ "$USE_UNIFIED" = true ] && echo "Unified v2.0" || echo "Legacy")"

# Source .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Check for required API keys
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    echo "Please set it in a .env file or export it directly."
    exit 1
fi

if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "Error: ELEVENLABS_API_KEY environment variable is not set."
    echo "Please set it in a .env file or export it directly."
    exit 1
fi

# Run the setup script if directories don't exist
if [ ! -d "assets" ] || [ ! -d "output" ] || [ ! -d "temp" ]; then
    echo "Running setup script to create required directories"
    python setup.py
fi

# Choose processor and run
if [ "$USE_UNIFIED" = true ]; then
    # Use new unified processor
    echo ""
    echo "🚀 Starting Factual Pipeline v2.0 with Unified Processor"
    echo "Features: HTML summaries, engagement metrics, proper session isolation"
    echo ""
    
    if [ "$MODE" = "batch" ]; then
        if [ -z "$CONFIG_FILE" ]; then
            echo "Running unified batch processing on: $BATCH_FILE"
            python -c "
from unified_processor import FactualProcessor
import sys
try:
    processor = FactualProcessor()
    results = processor.process('$BATCH_FILE', mode='batch')
    print(f\"\\n✅ Batch processing complete!\")
    print(f\"Total URLs: {results.get('total_urls', 0)}\")
    print(f\"Successful: {results.get('successful', 0)}\")
    print(f\"Failed: {results.get('failed', 0)}\")
    if results.get('total_urls', 0) > 0:
        print(f\"Success Rate: {(results.get('successful', 0) / results.get('total_urls', 1) * 100):.1f}%\")
    print(f\"Output Directory: {results.get('batch_output_dir', 'Unknown')}\")
    print(f\"\\nGenerated Files:\")
    if results.get('batch_html_summary'):
        print(f\"  📊 HTML Summary: {results['batch_html_summary']}\")
    if results.get('batch_metrics_csv'):
        print(f\"  📈 Metrics CSV: {results['batch_metrics_csv']}\")
    if results.get('batch_text_summary'):
        print(f\"  📝 Text Summary: {results['batch_text_summary']}\")
except Exception as e:
    print(f\"❌ Error: {str(e)}\")
    sys.exit(1)
"
        else
            echo "Running unified batch processing on: $BATCH_FILE with config: $CONFIG_FILE"
            python -c "
from unified_processor import FactualProcessor
import sys
try:
    processor = FactualProcessor('$CONFIG_FILE')
    results = processor.process('$BATCH_FILE', mode='batch')
    print(f\"\\n✅ Batch processing complete!\")
    print(f\"Total URLs: {results.get('total_urls', 0)}\")
    print(f\"Successful: {results.get('successful', 0)}\")
    print(f\"Failed: {results.get('failed', 0)}\")
    if results.get('total_urls', 0) > 0:
        print(f\"Success Rate: {(results.get('successful', 0) / results.get('total_urls', 1) * 100):.1f}%\")
    print(f\"Output Directory: {results.get('batch_output_dir', 'Unknown')}\")
    print(f\"\\nGenerated Files:\")
    if results.get('batch_html_summary'):
        print(f\"  📊 HTML Summary: {results['batch_html_summary']}\")
    if results.get('batch_metrics_csv'):
        print(f\"  📈 Metrics CSV: {results['batch_metrics_csv']}\")
    if results.get('batch_text_summary'):
        print(f\"  📝 Text Summary: {results['batch_text_summary']}\")
except Exception as e:
    print(f\"❌ Error: {str(e)}\")
    sys.exit(1)
"
        fi
    else
        if [ -z "$CONFIG_FILE" ]; then
            echo "Running unified single processing on: $URL"
            python -c "
from unified_processor import FactualProcessor
import sys
try:
    processor = FactualProcessor()
    result = processor.process('$URL', mode='single')
    print(f\"\\n✅ Processing complete!\")
    print(f\"URL: $URL\")
    print(f\"Output Directory: {result.get('output_directory', 'Unknown')}\")
    print(f\"\\nGenerated Files:\")
    if result.get('output_video'):
        print(f\"  🎥 Video: {result['output_video']}\")
    if result.get('html_summary'):
        print(f\"  📄 HTML Summary: {result['html_summary']}\")
    if result.get('instagram_description'):
        print(f\"  📱 IG Description: {result['instagram_description']}\")
    if result.get('metrics_file'):
        print(f\"  📊 Metrics: {result['metrics_file']}\")
except Exception as e:
    print(f\"❌ Error: {str(e)}\")
    sys.exit(1)
"
        else
            echo "Running unified single processing on: $URL with config: $CONFIG_FILE"
            python -c "
from unified_processor import FactualProcessor
import sys
try:
    processor = FactualProcessor('$CONFIG_FILE')
    result = processor.process('$URL', mode='single')
    print(f\"\\n✅ Processing complete!\")
    print(f\"URL: $URL\")
    print(f\"Output Directory: {result.get('output_directory', 'Unknown')}\")
    print(f\"\\nGenerated Files:\")
    if result.get('output_video'):
        print(f\"  🎥 Video: {result['output_video']}\")
    if result.get('html_summary'):
        print(f\"  📄 HTML Summary: {result['html_summary']}\")
    if result.get('instagram_description'):
        print(f\"  📱 IG Description: {result['instagram_description']}\")
    if result.get('metrics_file'):
        print(f\"  📊 Metrics: {result['metrics_file']}\")
except Exception as e:
    print(f\"❌ Error: {str(e)}\")
    sys.exit(1)
"
        fi
    fi
else
    # Use legacy processor
    echo ""
    echo "⚠️  Using Legacy Processor"
    echo "Note: Legacy mode has the batch processing bug. Use --unified for proper batch processing."
    echo ""
    
    if [ "$MODE" = "batch" ]; then
        if [ -z "$CONFIG_FILE" ]; then
            echo "Running legacy batch processing on: $BATCH_FILE"
            python factual_pipeline.py --batch "$BATCH_FILE"
        else
            echo "Running legacy batch processing on: $BATCH_FILE with config: $CONFIG_FILE"
            python factual_pipeline.py --batch "$BATCH_FILE" --config "$CONFIG_FILE"
        fi
    else
        if [ -z "$CONFIG_FILE" ]; then
            echo "Running legacy single processing on: $URL"
            python factual_pipeline.py "$URL"
        else
            echo "Running legacy single processing on: $URL with config: $CONFIG_FILE"
            python factual_pipeline.py "$URL" --config "$CONFIG_FILE"
        fi
    fi
fi

echo ""
echo "🎉 Factual Pipeline execution complete!"
