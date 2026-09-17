# Agentic Workflow for Factual Reel Generation and Instagram Posting

An intelligent, automated workflow that processes Instagram reels end-to-end: from input URLs to generating fact-checked content and automatically posting enhanced reels to Instagram.

## 🎯 Overview

This agentic workflow orchestrates the complete process:

1. **Input**: List of Instagram/Facebook reel URLs
2. **Processing**: Downloads and processes each reel through the factual pipeline
3. **Fact-Checking**: Generates AI-powered fact-checking interventions with sources
4. **Enhancement**: Creates enhanced videos with embedded corrections and confirmations
5. **Publishing**: Automatically uploads and posts the enhanced reels to Instagram
6. **Monitoring**: Tracks progress and provides detailed status reports

## 🚀 Key Features

- **Autonomous Operation**: Fully automated processing from input to Instagram posting
- **Concurrent Processing**: Process multiple reels simultaneously with configurable concurrency
- **Quality Control**: Validates output quality before posting (minimum interventions, duration limits)
- **State Persistence**: Resumable workflows with automatic state saving/loading
- **Multiple Upload Providers**: Support for Cloudinary, AWS S3, or file sharing services
- **Rate Limiting**: Intelligent delays between posts to respect Instagram limits
- **Error Handling**: Robust error handling with retry mechanisms and detailed logging
- **Progress Tracking**: Real-time status updates and comprehensive reporting

## 📋 Prerequisites

1. **Python 3.10+** with the root requirements installed (`pip install -r requirements.txt`)
2. **Existing Factual Pipeline** (MVP/factual directory)
3. **Instagram Business Account** with Graph API access
4. **File Storage Service** (Cloudinary, AWS S3, or similar)
5. **API Keys** for OpenAI, ElevenLabs, Instagram, and file storage

## 🛠️ Installation

1. **Clone and setup the base project**:
   ```bash
   # Ensure you have the Factual project with MVP/factual directory
   # The agentic workflow builds on the existing pipeline
   ```

2. **Install additional dependencies**:
   ```bash
   pip install -r requirements.txt  # includes cloudinary and boto3 upload providers
   ```

3. **Place workflow files in project root**:
   ```bash
   # Ensure these files are in the same directory as MVP/
   # - agentic_workflow.py
   # - file_uploader.py
   ```

## ⚙️ Configuration

### 1. Create Workflow Configuration

```bash
python agentic_workflow.py create-config --output workflow_config.json
```

### 2. Edit Configuration File

```json
{
  "factual_config_path": "MVP/factual/config.json",
  "instagram_access_token": "YOUR_INSTAGRAM_ACCESS_TOKEN",
  "instagram_business_user_id": "YOUR_BUSINESS_USER_ID",
  "file_upload_config": {
    "type": "cloudinary",
    "cloud_name": "YOUR_CLOUDINARY_CLOUD_NAME",
    "api_key": "YOUR_CLOUDINARY_API_KEY",
    "api_secret": "YOUR_CLOUDINARY_API_SECRET"
  },
  "max_concurrent_tasks": 2,
  "enable_auto_posting": false,
  "posting_delay_minutes": 30,
  "min_intervention_count": 1,
  "max_video_duration_seconds": 180,
  "workflow_output_dir": "workflow_output",
  "keep_intermediate_files": true,
  "enable_webhook_notifications": false,
  "webhook_url": ""
}
```

### 3. Configure Upload Provider

#### Option A: Cloudinary
```json
"file_upload_config": {
  "type": "cloudinary",
  "cloud_name": "your-cloud-name",
  "api_key": "your-api-key",
  "api_secret": "your-api-secret"
}
```

#### Option B: AWS S3
```json
"file_upload_config": {
  "type": "s3",
  "bucket_name": "your-bucket-name",
  "region": "us-east-1",
  "access_key_id": "your-access-key",
  "secret_access_key": "your-secret-key"
}
```

#### Option C: File Sharing Service
```json
"file_upload_config": {
  "type": "fileshare",
  "service_url": "https://file.io"
}
```

## 🎬 Usage

### 1. Add Reel URLs to Processing Queue

#### From Command Line:
```bash
python agentic_workflow.py --config workflow_config.json add --urls \
  "https://www.instagram.com/reel/EXAMPLE1/" \
  "https://www.instagram.com/reel/EXAMPLE2/" \
  "https://www.facebook.com/watch?v=EXAMPLE3"
```

#### From File:
```bash
# Create a file with URLs (one per line)
echo "https://www.instagram.com/reel/EXAMPLE1/" > reel_urls.txt
echo "https://www.instagram.com/reel/EXAMPLE2/" >> reel_urls.txt

python agentic_workflow.py --config workflow_config.json add --file reel_urls.txt
```

### 2. Run the Complete Workflow

#### Process Without Auto-Posting (Safe Mode):
```bash
python agentic_workflow.py --config workflow_config.json run --no-auto-post
```

#### Process With Auto-Posting (Production Mode):
```bash
# First enable auto-posting in config.json: "enable_auto_posting": true
python agentic_workflow.py --config workflow_config.json run
```

#### With Custom Concurrency:
```bash
python agentic_workflow.py --config workflow_config.json run --concurrent 4
```

### 3. Monitor Progress

```bash
python agentic_workflow.py --config workflow_config.json status
```

## 📁 Output Structure

Each workflow run creates a timestamped directory:

```
workflow_output/20250714121435/
├── workflow_state.json          # Persistent workflow state
├── workflow_summary.json        # Final execution summary
├── task_001_reel_example/       # Individual reel outputs
│   ├── factual_output.mp4       # Enhanced video with fact-checks
│   ├── factual_output.json      # Detailed manifest
│   ├── factual_summary_slide.png # Summary slide
│   └── sources.txt              # Source citations
├── task_002_reel_another/
│   └── ... (similar structure)
└── workflow.log                 # Detailed execution logs
```

## 🔧 Workflow Configuration Options

### Quality Control Parameters

- **`min_intervention_count`**: Minimum fact-check interventions required (default: 1)
- **`max_video_duration_seconds`**: Skip videos longer than this (default: 180)

### Processing Parameters

- **`max_concurrent_tasks`**: Maximum simultaneous reel processing (default: 2)
- **`posting_delay_minutes`**: Delay between Instagram posts (default: 30)

### Safety Parameters

- **`enable_auto_posting`**: Global switch for automatic Instagram posting (default: false)
- **`keep_intermediate_files`**: Whether to keep processing artifacts (default: true)

## 🔄 Workflow States

Each reel task progresses through these states:

1. **`pending`**: Queued for processing
2. **`processing`**: Being processed through factual pipeline
3. **`fact_checked`**: Successfully processed, ready for posting
4. **`posting`**: Being uploaded to Instagram
5. **`posted`**: Successfully posted to Instagram
6. **`failed`**: Processing or posting failed

## 📊 Monitoring and Logging

### Real-time Status
```bash
# Get current workflow status
python agentic_workflow.py --config workflow_config.json status
```

### Logs
- **Console output**: Real-time progress updates
- **`workflow.log`**: Detailed execution logs
- **`workflow_state.json`**: Persistent state for resumability
- **`workflow_summary.json`**: Final execution summary

### Example Status Output
```
Workflow ID: 20250714_121435
Total tasks: 5

Tasks by status:
  posted: 3
  processing: 1
  pending: 1

Last updated: 2025-01-14T12:30:45
Output directory: workflow_output/20250714_121435
```

## 🚨 Safety Features

### Auto-Posting Safety
- **Disabled by default**: `enable_auto_posting: false`
- **Rate limiting**: Configurable delays between posts
- **Quality validation**: Only posts reels meeting quality requirements
- **Manual override**: `--no-auto-post` flag to disable posting

### Error Handling
- **Graceful failures**: Individual reel failures don't stop the workflow
- **Retry mechanisms**: Automatic retries for transient failures
- **State persistence**: Resume workflows after interruptions
- **Detailed error reporting**: Clear error messages and logging

## 🔍 Troubleshooting

### Common Issues

1. **Import Errors**:
   ```bash
   # Ensure you're running from the project root directory
   # MVP/factual directory should be accessible
   ```

2. **API Key Issues**:
   ```bash
   # Verify all API keys in configuration
   # Check Instagram Graph API permissions
   # Ensure file upload service credentials are correct
   ```

3. **Upload Failures**:
   ```bash
   # Verify file upload configuration
   # Check network connectivity to storage service
   # Ensure sufficient storage quota
   ```

4. **Instagram Posting Failures**:
   ```bash
   # Verify Instagram Business Account setup
   # Check Graph API permissions and token validity
   # Ensure videos meet Instagram requirements
   ```

### Debug Mode

Enable detailed logging:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/MVP/factual
python agentic_workflow.py --config workflow_config.json run --no-auto-post
```

### State Recovery

If a workflow is interrupted:
```bash
# The workflow automatically resumes from the last saved state
python agentic_workflow.py --config workflow_config.json run
```

## 🤖 Advanced Usage

### Programmatic API

```python
from agentic_workflow import AgenticWorkflow, WorkflowConfig

# Initialize workflow
config = WorkflowConfig.from_file("workflow_config.json")
workflow = AgenticWorkflow(config)

# Add URLs
task_ids = workflow.add_reel_urls([
    "https://www.instagram.com/reel/EXAMPLE1/",
    "https://www.instagram.com/reel/EXAMPLE2/"
])

# Run workflow
import asyncio
summary = asyncio.run(workflow.run_workflow())

print(f"Processed {summary['total_tasks']} reels")
print(f"Success rate: {summary['success_rate']:.1%}")
```

### Custom Upload Providers

Implement custom file uploaders:
```python
from file_uploader import FileUploader

class CustomUploader(FileUploader):
    def upload_file(self, file_path: str, content_type: str) -> str:
        # Your custom upload logic
        return "https://your-service.com/uploaded-file-url"
```

## 📞 Support

For issues and questions:
- Check the main project README for Factual pipeline setup
- Review workflow logs for detailed error information
- Ensure all API credentials are properly configured
- Verify Instagram Business Account permissions

## 🙏 Acknowledgments

This agentic workflow builds upon the Factual project's core capabilities:
- OpenAI for GPT-4o and Whisper APIs
- ElevenLabs for TTS technology
- Instagram Graph API for social media publishing
- Various cloud storage providers for file hosting

---

**Agentic Workflow** - Automating factual content creation and distribution at scale.