#!/bin/bash
# Wrapper script for the Factual pipeline

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
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 https://www.instagram.com/reel/ABC123/"
    echo "  $0 --batch urls.txt"
    echo "  $0 --batch urls.txt config.json"
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

# Check for batch mode
if [ "$1" = "--batch" ]; then
    if [ $# -lt 2 ]; then
        echo "Error: Batch mode requires a batch file argument"
        echo ""
        show_usage
        exit 1
    fi
    
    BATCH_FILE=$2
    CONFIG_FILE=$3
    MODE="batch"
    
    # Check if batch file exists
    if [ ! -f "$BATCH_FILE" ]; then
        echo "Error: Batch file '$BATCH_FILE' not found"
        exit 1
    fi
    
    echo "Batch processing mode"
    echo "Batch file: $BATCH_FILE"
    
else
    # Single URL mode
URL=$1
CONFIG_FILE=$2
    MODE="single"
    
    echo "Single URL processing mode"
    echo "URL: $URL"
fi

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

# Run the pipeline based on mode
if [ "$MODE" = "batch" ]; then
    if [ -z "$CONFIG_FILE" ]; then
        echo "Running Factual pipeline in batch mode on: $BATCH_FILE"
        python factual_pipeline.py --batch "$BATCH_FILE"
    else
        echo "Running Factual pipeline in batch mode on: $BATCH_FILE with config: $CONFIG_FILE"
        python factual_pipeline.py --batch "$BATCH_FILE" --config "$CONFIG_FILE"
    fi
else
if [ -z "$CONFIG_FILE" ]; then
    echo "Running Factual pipeline on: $URL"
    python factual_pipeline.py "$URL"
else
    echo "Running Factual pipeline on: $URL with config: $CONFIG_FILE"
    python factual_pipeline.py "$URL" --config "$CONFIG_FILE"
    fi
fi 