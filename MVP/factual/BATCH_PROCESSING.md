# Batch Processing Guide

The Factual pipeline now supports batch processing, allowing you to process multiple reels from a text file in a single operation.

## Quick Start

### 1. Create a batch file
Create a text file with one URL per line:

```
# my_reels.txt
https://www.instagram.com/reel/ABC123/
https://www.instagram.com/reel/DEF456/
https://www.instagram.com/reel/GHI789/
```

### 2. Run batch processing

**Using the shell script:**
```bash
./run_factual.sh --batch my_reels.txt
```

**Using Python directly:**
```bash
python factual_pipeline.py --batch my_reels.txt
```

## Batch File Format

- **One URL per line**: Each line should contain a single Instagram or Facebook reel URL
- **Comments**: Lines starting with `#` are treated as comments and ignored
- **Empty lines**: Empty lines are ignored
- **URL format**: Both Instagram and Facebook URLs are supported

### Example batch file:
```
# My reels to fact-check
https://www.instagram.com/reel/DE_C78HyOVM/
https://www.instagram.com/reel/EXAMPLE123/

# Facebook reels also work
https://www.facebook.com/watch?v=123456789

# Add as many as needed
https://www.instagram.com/reel/ANOTHER456/
```

## Output Structure

When processing in batch mode, the pipeline creates a timestamped output directory:

```
output/
└── batch_20231215_143022/
    ├── 001_DE_C78HyOVM/          # First reel (line 1)
    │   ├── input_video.mp4
    │   ├── output_video.mp4
    │   ├── manifest.json
    │   └── preview.json
    ├── 002_EXAMPLE123/           # Second reel (line 2)
    │   ├── input_video.mp4
    │   ├── output_video.mp4
    │   ├── manifest.json
    │   └── preview.json
    ├── 003_123456789/            # Third reel (line 4, Facebook)
    │   └── ...
    ├── batch_summary.json        # Detailed JSON summary
    └── batch_summary.txt         # Human-readable summary
```

## Command Line Options

All regular pipeline options work with batch processing:

```bash
# With custom config
./run_factual.sh --batch my_reels.txt config.json

# With debugging enabled
python factual_pipeline.py --batch my_reels.txt --debug-all

# Disable text rendering
python factual_pipeline.py --batch my_reels.txt --no-text

# Disable summary frames
python factual_pipeline.py --batch my_reels.txt --no-summary
```

## Error Handling

- **Failed URLs**: If some URLs fail to process, the batch continues with remaining URLs
- **Error tracking**: All errors are logged and included in the batch summary
- **Individual outputs**: Successfully processed reels still generate their output artifacts
- **Summary report**: Both JSON and text summaries show success/failure statistics

## Batch Summary

After processing, you'll get:

### Console Output:
```
Batch processing complete!
Total URLs: 5
Successful: 4
Failed: 1
Success Rate: 80.0%
Batch output directory: output/batch_20231215_143022
```

### JSON Summary (`batch_summary.json`):
```json
{
  "batch_info": {
    "batch_file": "my_reels.txt",
    "processed_at": "2023-12-15T14:30:22",
    "total_urls": 5,
    "successful": 4,
    "failed": 1,
    "success_rate": "80.0%"
  },
  "successful_results": [...],
  "failed_results": [...]
}
```

### Text Summary (`batch_summary.txt`):
Human-readable report with details of all processed reels and any failures.

## Best Practices

### 1. Start Small
Test with a few URLs first to ensure your setup is working correctly:
```
# test_batch.txt
https://www.instagram.com/reel/DE_C78HyOVM/  # Known working test URL
```

### 2. Clean URLs
Remove tracking parameters when possible:
```
# Good
https://www.instagram.com/reel/ABC123/

# Also works, but unnecessary parameters
https://www.instagram.com/reel/ABC123/?igsh=MWh5dTU4NzltM296Zw==
```

### 3. Monitor Progress
The pipeline logs progress for each URL:
```
INFO - Processing URL 1/5 (line 1): https://www.instagram.com/reel/ABC123/
INFO - Successfully processed reel 1: https://www.instagram.com/reel/ABC123/
INFO - Processing URL 2/5 (line 2): https://www.instagram.com/reel/DEF456/
```

### 4. Handle API Limits
Be mindful of API rate limits:
- **OpenAI**: Has generous limits, but large batches may take time
- **ElevenLabs**: Check your character limits in the API dashboard

## Troubleshooting

### Common Issues:

1. **"Batch file not found"**
   - Check the file path is correct
   - Ensure the file exists and is readable

2. **"No URLs found in batch file"**
   - Make sure URLs aren't all commented out with `#`
   - Check for proper line endings (especially on Windows)

3. **All URLs failing with same error**
   - Check your API keys are configured correctly
   - Verify your internet connection
   - Test with a single URL first

4. **Some URLs failing**
   - Check the failed URLs in the summary report
   - Some Instagram/Facebook URLs may be private or deleted
   - Retry failed URLs individually to debug

### Debug Mode:
Enable debugging to get more detailed information:
```bash
python factual_pipeline.py --batch my_reels.txt --debug-all
```

This will save debug information for each processed reel, helping identify issues.

## Integration with Existing Workflow

The batch processing feature is fully compatible with your existing single-URL workflow:

```bash
# Single URL (existing workflow)
./run_factual.sh https://www.instagram.com/reel/ABC123/

# Batch processing (new feature)
./run_factual.sh --batch urls.txt

# Both support the same options
./run_factual.sh https://www.instagram.com/reel/ABC123/ config.json
./run_factual.sh --batch urls.txt config.json
``` 