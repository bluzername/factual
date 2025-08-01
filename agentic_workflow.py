#!/usr/bin/env python3
"""
Agentic Workflow for End-to-End Factual Reel Generation and Instagram Posting

This workflow orchestrates the complete process:
1. Input: List of reel links
2. Download and process each reel through the factual pipeline
3. Generate fact-checked videos with interventions
4. Automatically post the enhanced reels to Instagram
5. Track and manage the entire workflow with status updates
"""

import os
import sys
import json
import logging
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import requests
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes

# Add the MVP/factual directory to path to import the existing pipeline
sys.path.append(str(Path(__file__).parent / "MVP" / "factual"))

try:
    from factual_pipeline import FactualPipeline
except ImportError as e:
    print(f"Error importing FactualPipeline: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Import file uploader
try:
    from file_uploader import create_uploader, FileUploader
except ImportError as e:
    print(f"Error importing file_uploader: {e}")
    print("Make sure file_uploader.py is in the same directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("workflow.log")
    ]
)
logger = logging.getLogger("agentic_workflow")

@dataclass
class ReelProcessingTask:
    """Represents a single reel processing task."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_url: str = ""
    status: str = "pending"  # pending, processing, fact_checked, posting, posted, failed
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Processing results
    factual_video_path: Optional[str] = None
    manifest_path: Optional[str] = None
    summary_slide_path: Optional[str] = None
    sources_file: Optional[str] = None
    
    # Instagram posting results
    instagram_media_id: Optional[str] = None
    instagram_post_url: Optional[str] = None
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def update_status(self, status: str, error_message: Optional[str] = None):
        """Update task status and timestamp."""
        self.status = status
        self.updated_at = datetime.now()
        if error_message:
            self.error_message = error_message
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

@dataclass
class WorkflowConfig:
    """Configuration for the agentic workflow."""
    # Factual Pipeline Config - can be a path or embedded config
    factual_config_path: Optional[str] = None
    factual_config: Optional[Dict[str, Any]] = None
    
    # Instagram API Configuration
    instagram_access_token: str = ""
    instagram_business_user_id: str = ""
    
    # File Upload Configuration
    file_upload_config: Optional[Dict[str, Any]] = None
    
    # Workflow Settings
    max_concurrent_tasks: int = 2
    enable_auto_posting: bool = False  # Safety switch for auto-posting
    posting_delay_minutes: int = 30  # Delay between posts to avoid rate limits
    
    # Quality Control
    min_intervention_count: int = 1  # Minimum fact-check interventions required
    max_video_duration_seconds: int = 180  # Skip videos longer than this
    
    # Output Settings
    workflow_output_dir: str = "workflow_output"
    keep_intermediate_files: bool = True
    
    # Monitoring
    enable_webhook_notifications: bool = False
    webhook_url: str = ""
    
    @classmethod
    def from_file(cls, config_path: str) -> 'WorkflowConfig':
        """Load configuration from JSON file."""
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Check if this is a factual pipeline config or workflow config
        factual_keys = {'openai_api_key', 'elevenlabs_api_key', 'whisper_model', 'watermark_path', 'ffmpeg_path', 'yt_dlp_path'}
        workflow_keys = {'factual_config_path', 'instagram_access_token', 'max_concurrent_tasks', 'enable_auto_posting'}
        
        if any(key in config_data for key in factual_keys) and not any(key in config_data for key in workflow_keys):
            # This is a factual pipeline config file, use it as embedded config
            logger.info("Detected factual pipeline config, using as embedded configuration")
            return cls(factual_config=config_data)
        else:
            # This is a workflow config file
            return cls(**config_data)
    
    def save_to_file(self, config_path: str):
        """Save configuration to JSON file."""
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

class InstagramPublisher:
    """Handles Instagram posting functionality using the Instagram Graph API."""
    
    def __init__(self, access_token: str, business_user_id: str, file_uploader: Optional[FileUploader] = None):
        """Initialize Instagram publisher.
        
        Args:
            access_token: Instagram Graph API access token
            business_user_id: Instagram business account user ID
            file_uploader: File uploader instance for hosting media files
        """
        self.access_token = access_token
        self.business_user_id = business_user_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self.file_uploader = file_uploader
        
    def upload_reel(self, video_path: str, caption: str, cover_image_path: Optional[str] = None) -> Dict[str, Any]:
        """Upload a reel to Instagram.
        
        Args:
            video_path: Path to the video file
            caption: Caption for the reel
            cover_image_path: Optional path to cover image
            
        Returns:
            Dictionary with upload results including media ID
        """
        logger.info(f"Starting Instagram reel upload: {video_path}")
        
        try:
            # Step 1: Create media container
            container_id = self._create_media_container(video_path, caption, cover_image_path)
            
            # Step 2: Check container status and publish when ready
            media_id = self._publish_media_container(container_id)
            
            # Step 3: Get the published media details
            media_details = self._get_media_details(media_id)
            
            return {
                'success': True,
                'media_id': media_id,
                'permalink': media_details.get('permalink', ''),
                'container_id': container_id
            }
            
        except Exception as e:
            logger.error(f"Instagram upload failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_media_container(self, video_path: str, caption: str, cover_image_path: Optional[str] = None) -> str:
        """Create a media container for the reel."""
        # First, upload the video file
        video_url = self._upload_video_file(video_path)
        
        # Create container parameters
        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'access_token': self.access_token
        }
        
        # Add cover image if provided
        if cover_image_path and os.path.exists(cover_image_path):
            cover_url = self._upload_image_file(cover_image_path)
            params['thumb_offset'] = '0'  # Use uploaded cover instead of auto-generated
        
        # Create the container
        response = requests.post(
            f"{self.base_url}/{self.business_user_id}/media",
            data=params
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to create media container: {response.text}")
        
        result = response.json()
        return result['id']
    
    def _upload_video_file(self, video_path: str) -> str:
        """Upload video file and return the URL."""
        if not self.file_uploader:
            # Fallback placeholder implementation
            logger.warning("Video upload to public URL not implemented - using placeholder")
            return f"https://your-storage-service.com/videos/{os.path.basename(video_path)}"
        
        # Use the configured file uploader
        content_type = mimetypes.guess_type(video_path)[0] or 'video/mp4'
        return self.file_uploader.upload_file(video_path, content_type)
    
    def _upload_image_file(self, image_path: str) -> str:
        """Upload image file and return the URL."""
        if not self.file_uploader:
            # Fallback placeholder implementation
            logger.warning("Image upload to public URL not implemented - using placeholder")
            return f"https://your-storage-service.com/images/{os.path.basename(image_path)}"
        
        # Use the configured file uploader
        content_type = mimetypes.guess_type(image_path)[0] or 'image/png'
        return self.file_uploader.upload_file(image_path, content_type)
    
    def _publish_media_container(self, container_id: str) -> str:
        """Publish the media container and return media ID."""
        # Wait for container to be ready
        max_attempts = 30
        for attempt in range(max_attempts):
            status = self._check_container_status(container_id)
            if status == 'FINISHED':
                break
            elif status == 'ERROR':
                raise Exception(f"Media container processing failed: {container_id}")
            
            time.sleep(10)  # Wait 10 seconds between checks
        else:
            raise Exception(f"Media container did not finish processing in time: {container_id}")
        
        # Publish the container
        response = requests.post(
            f"{self.base_url}/{self.business_user_id}/media_publish",
            data={
                'creation_id': container_id,
                'access_token': self.access_token
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to publish media: {response.text}")
        
        result = response.json()
        return result['id']
    
    def _check_container_status(self, container_id: str) -> str:
        """Check the status of a media container."""
        response = requests.get(
            f"{self.base_url}/{container_id}",
            params={
                'fields': 'status_code',
                'access_token': self.access_token
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to check container status: {response.text}")
        
        result = response.json()
        return result.get('status_code', 'UNKNOWN')
    
    def _get_media_details(self, media_id: str) -> Dict[str, Any]:
        """Get details of published media."""
        response = requests.get(
            f"{self.base_url}/{media_id}",
            params={
                'fields': 'id,permalink,media_type,timestamp',
                'access_token': self.access_token
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get media details: {response.text}")
        
        return response.json()

class AgenticWorkflow:
    """Main agentic workflow orchestrator."""
    
    def __init__(self, config: WorkflowConfig, workflow_id: Optional[str] = None):
        """Initialize the workflow with configuration.
        
        Args:
            config: Workflow configuration
            workflow_id: Optional specific workflow ID to resume, or None to auto-detect/create
        """
        self.config = config
        self.tasks: List[ReelProcessingTask] = []
        
        # Handle workflow ID - either provided, auto-detect latest, or create new
        if workflow_id:
            self.workflow_id = workflow_id
        else:
            # Try to find the most recent workflow to resume
            existing_workflow = self._find_latest_workflow()
            if existing_workflow:
                self.workflow_id = existing_workflow
                logger.info(f"Resuming existing workflow: {self.workflow_id}")
            else:
                self.workflow_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                logger.info(f"Creating new workflow: {self.workflow_id}")
        
        # Create output directory
        self.output_dir = Path(config.workflow_output_dir) / self.workflow_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize factual pipeline with proper config handling
        if config.factual_config:
            # Create a temporary config file for the embedded config
            temp_config_dir = Path(tempfile.gettempdir()) / "factual_workflow"
            temp_config_dir.mkdir(exist_ok=True)
            temp_config_path = temp_config_dir / f"factual_config_{self.workflow_id}.json"
            
            with open(temp_config_path, 'w') as f:
                json.dump(config.factual_config, f, indent=2)
            
            self.factual_pipeline = FactualPipeline(str(temp_config_path))
            self.temp_config_path = temp_config_path  # Keep reference for cleanup
        elif config.factual_config_path:
            self.factual_pipeline = FactualPipeline(config.factual_config_path)
            self.temp_config_path = None
        else:
            # Use default config
            self.factual_pipeline = FactualPipeline()
            self.temp_config_path = None
        
        # Initialize file uploader if configured
        self.file_uploader = None
        if config.file_upload_config:
            try:
                self.file_uploader = create_uploader(config.file_upload_config)
                logger.info(f"Initialized file uploader: {config.file_upload_config.get('type', 'unknown')}")
            except Exception as e:
                logger.warning(f"Failed to initialize file uploader: {e}")
        
        if config.enable_auto_posting and config.instagram_access_token:
            self.instagram_publisher = InstagramPublisher(
                config.instagram_access_token,
                config.instagram_business_user_id,
                self.file_uploader
            )
        else:
            self.instagram_publisher = None
            logger.info("Instagram auto-posting disabled or missing credentials")
        
        # Setup state persistence
        self.state_file = self.output_dir / "workflow_state.json"
        self.load_state()
        
        logger.info(f"Initialized agentic workflow {self.workflow_id}")
    
    def _find_latest_workflow(self) -> Optional[str]:
        """Find the most recent workflow that has pending tasks.
        
        Returns:
            Workflow ID of the latest workflow with pending tasks, or None
        """
        workflow_base_dir = Path(self.config.workflow_output_dir)
        if not workflow_base_dir.exists():
            return None
        
        # Get all workflow directories sorted by creation time (newest first)
        workflow_dirs = []
        for item in workflow_base_dir.iterdir():
            if item.is_dir() and item.name.replace('_', '').isdigit():
                workflow_dirs.append(item.name)
        
        workflow_dirs.sort(reverse=True)
        
        # Check each workflow for pending tasks
        for workflow_id in workflow_dirs:
            state_file = workflow_base_dir / workflow_id / "workflow_state.json"
            if state_file.exists():
                try:
                    with open(state_file, 'r') as f:
                        state_data = json.load(f)
                    
                    # Check if there are pending tasks
                    pending_tasks = [
                        task for task in state_data.get('tasks', [])
                        if task.get('status') == 'pending'
                    ]
                    
                    if pending_tasks:
                        logger.info(f"Found workflow {workflow_id} with {len(pending_tasks)} pending tasks")
                        return workflow_id
                        
                except Exception as e:
                    logger.warning(f"Failed to read state file for workflow {workflow_id}: {e}")
        
        return None
    
    def load_state(self):
        """Load workflow state from disk if it exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Reconstruct tasks from saved state
                self.tasks = []
                for task_data in state_data.get('tasks', []):
                    task = ReelProcessingTask(**task_data)
                    # Convert ISO strings back to datetime
                    task.created_at = datetime.fromisoformat(task_data['created_at'])
                    task.updated_at = datetime.fromisoformat(task_data['updated_at'])
                    self.tasks.append(task)
                
                logger.info(f"Loaded {len(self.tasks)} tasks from previous state")
            except Exception as e:
                logger.error(f"Failed to load workflow state: {e}")
    
    def save_state(self):
        """Save current workflow state to disk."""
        try:
            state_data = {
                'workflow_id': self.workflow_id,
                'timestamp': datetime.now().isoformat(),
                'tasks': [task.to_dict() for task in self.tasks]
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save workflow state: {e}")
    
    def add_reel_urls(self, urls: List[str]) -> List[str]:
        """Add reel URLs to the processing queue.
        
        Args:
            urls: List of Instagram/Facebook reel URLs
            
        Returns:
            List of task IDs created
        """
        task_ids = []
        
        for url in urls:
            # Skip if URL already exists
            if any(task.source_url == url for task in self.tasks):
                logger.info(f"URL already in queue: {url}")
                continue
            
            task = ReelProcessingTask(source_url=url)
            self.tasks.append(task)
            task_ids.append(task.id)
            
            logger.info(f"Added reel to queue: {url} (Task ID: {task.id})")
        
        self.save_state()
        return task_ids
    
    def add_reel_urls_from_file(self, file_path: str) -> List[str]:
        """Add reel URLs from a batch file.
        
        Args:
            file_path: Path to file containing URLs (one per line)
            
        Returns:
            List of task IDs created
        """
        urls = []
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        
        logger.info(f"Loaded {len(urls)} URLs from file: {file_path}")
        return self.add_reel_urls(urls)
    
    async def run_workflow(self, max_concurrent: Optional[int] = None) -> Dict[str, Any]:
        """Run the complete workflow for all pending tasks.
        
        Args:
            max_concurrent: Maximum number of concurrent tasks (overrides config)
            
        Returns:
            Workflow execution summary
        """
        concurrent_limit = max_concurrent or self.config.max_concurrent_tasks
        
        logger.info(f"Starting workflow execution with {concurrent_limit} concurrent tasks")
        
        # Get pending tasks
        pending_tasks = [task for task in self.tasks if task.status == "pending"]
        
        if not pending_tasks:
            logger.info("No pending tasks to process")
            return self._generate_summary()
        
        # Process tasks with concurrency control
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def process_task_wrapper(task: ReelProcessingTask):
            async with semaphore:
                return await self._process_single_task(task)
        
        # Execute all tasks concurrently
        task_results = await asyncio.gather(
            *[process_task_wrapper(task) for task in pending_tasks],
            return_exceptions=True
        )
        
        # Process results
        for task, result in zip(pending_tasks, task_results):
            if isinstance(result, Exception):
                task.update_status("failed", str(result))
                logger.error(f"Task {task.id} failed: {result}")
            else:
                logger.info(f"Task {task.id} completed with status: {task.status}")
        
        self.save_state()
        
        # Auto-post to Instagram if enabled
        if self.config.enable_auto_posting and self.instagram_publisher:
            await self._auto_post_completed_reels()
        
        return self._generate_summary()
    
    async def _process_single_task(self, task: ReelProcessingTask) -> bool:
        """Process a single reel task through the factual pipeline.
        
        Args:
            task: The reel processing task
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Processing task {task.id}: {task.source_url}")
            task.update_status("processing")
            self.save_state()
            
            # Run the factual pipeline
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.factual_pipeline.process_reel,
                task.source_url
            )
            
            # Store results
            task.factual_video_path = result.get('output_video')
            task.manifest_path = result.get('manifest')
            task.summary_slide_path = result.get('summary_slide')
            
            # Check if there's a sources file
            if task.factual_video_path:
                output_dir = os.path.dirname(task.factual_video_path)
                sources_file = os.path.join(output_dir, 'sources.txt')
                if os.path.exists(sources_file):
                    task.sources_file = sources_file
            
            # Validate quality requirements
            if not self._validate_output_quality(task):
                task.update_status("failed", "Output did not meet quality requirements")
                return False
            
            task.update_status("fact_checked")
            logger.info(f"Successfully fact-checked task {task.id}")
            
            return True
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            task.update_status("failed", error_msg)
            logger.error(f"Task {task.id} failed: {error_msg}")
            return False
    
    def _validate_output_quality(self, task: ReelProcessingTask) -> bool:
        """Validate that the processed output meets quality requirements.
        
        Args:
            task: The completed task to validate
            
        Returns:
            True if output meets requirements, False otherwise
        """
        # Check that output file exists
        if not task.factual_video_path or not os.path.exists(task.factual_video_path):
            logger.warning(f"Output video not found for task {task.id}")
            return False
        
        # Check manifest for intervention count
        if task.manifest_path and os.path.exists(task.manifest_path):
            try:
                with open(task.manifest_path, 'r') as f:
                    manifest = json.load(f)
                
                intervention_count = len(manifest.get('interventions', []))
                if intervention_count < self.config.min_intervention_count:
                    logger.warning(f"Task {task.id} has only {intervention_count} interventions, minimum is {self.config.min_intervention_count}")
                    return False
                
                # Check video duration
                duration = manifest.get('total_duration_seconds', 0)
                if duration > self.config.max_video_duration_seconds:
                    logger.warning(f"Task {task.id} duration {duration}s exceeds maximum {self.config.max_video_duration_seconds}s")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to validate manifest for task {task.id}: {e}")
                return False
        
        return True
    
    async def _auto_post_completed_reels(self):
        """Automatically post fact-checked reels to Instagram."""
        if not self.instagram_publisher:
            logger.warning("Instagram publisher not available for auto-posting")
            return
        
        # Get tasks ready for posting
        ready_tasks = [
            task for task in self.tasks 
            if task.status == "fact_checked" and task.factual_video_path
        ]
        
        if not ready_tasks:
            logger.info("No reels ready for posting")
            return
        
        logger.info(f"Auto-posting {len(ready_tasks)} fact-checked reels")
        
        for i, task in enumerate(ready_tasks):
            try:
                task.update_status("posting")
                self.save_state()
                
                # Generate caption from sources
                caption = self._generate_instagram_caption(task)
                
                # Post to Instagram
                result = self.instagram_publisher.upload_reel(
                    task.factual_video_path,
                    caption,
                    task.summary_slide_path
                )
                
                if result['success']:
                    task.instagram_media_id = result['media_id']
                    task.instagram_post_url = result.get('permalink', '')
                    task.update_status("posted")
                    logger.info(f"Successfully posted task {task.id} to Instagram")
                else:
                    task.update_status("failed", f"Instagram upload failed: {result['error']}")
                    logger.error(f"Failed to post task {task.id}: {result['error']}")
                
                # Add delay between posts to avoid rate limits
                if i < len(ready_tasks) - 1:  # Don't delay after the last post
                    delay_seconds = self.config.posting_delay_minutes * 60
                    logger.info(f"Waiting {self.config.posting_delay_minutes} minutes before next post...")
                    await asyncio.sleep(delay_seconds)
                
            except Exception as e:
                task.update_status("failed", f"Auto-posting failed: {str(e)}")
                logger.error(f"Auto-posting failed for task {task.id}: {e}")
            
            self.save_state()
    
    def _generate_instagram_caption(self, task: ReelProcessingTask) -> str:
        """Generate Instagram caption from task sources and manifest.
        
        Args:
            task: The task to generate caption for
            
        Returns:
            Generated caption text
        """
        caption_parts = [
            "🔍 Fact-checked content alert! 📋",
            "",
            "This reel has been enhanced with factual corrections and verifications to help combat misinformation.",
            "",
        ]
        
        # Add sources if available
        if task.sources_file and os.path.exists(task.sources_file):
            try:
                with open(task.sources_file, 'r') as f:
                    sources_content = f.read().strip()
                
                if sources_content:
                    caption_parts.extend([
                        "📚 Sources:",
                        sources_content[:500] + "..." if len(sources_content) > 500 else sources_content,
                        ""
                    ])
            except Exception as e:
                logger.warning(f"Failed to read sources file for task {task.id}: {e}")
        
        caption_parts.extend([
            "#FactCheck #MisinformationAwareness #TruthMatters #FactualContent",
            "#MediaLiteracy #VerifiedFacts #ResponsibleSharing"
        ])
        
        return "\n".join(caption_parts)
    
    def cleanup(self):
        """Clean up temporary files and resources."""
        if hasattr(self, 'temp_config_path') and self.temp_config_path and self.temp_config_path.exists():
            try:
                self.temp_config_path.unlink()
                logger.info(f"Cleaned up temporary config file: {self.temp_config_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary config file: {e}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate workflow execution summary.
        
        Returns:
            Summary dictionary with statistics and results
        """
        total_tasks = len(self.tasks)
        status_counts = {}
        
        for task in self.tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
        
        summary = {
            'workflow_id': self.workflow_id,
            'total_tasks': total_tasks,
            'status_breakdown': status_counts,
            'success_rate': (status_counts.get('posted', 0) + status_counts.get('fact_checked', 0)) / total_tasks if total_tasks > 0 else 0,
            'completed_at': datetime.now().isoformat(),
            'output_directory': str(self.output_dir),
            'failed_tasks': [
                {
                    'id': task.id,
                    'url': task.source_url,
                    'error': task.error_message
                }
                for task in self.tasks if task.status == 'failed'
            ]
        }
        
        # Save summary to file
        summary_file = self.output_dir / "workflow_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Clean up temporary files
        self.cleanup()
        
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status.
        
        Returns:
            Current status dictionary
        """
        return {
            'workflow_id': self.workflow_id,
            'total_tasks': len(self.tasks),
            'tasks_by_status': {
                status: len([t for t in self.tasks if t.status == status])
                for status in ['pending', 'processing', 'fact_checked', 'posting', 'posted', 'failed']
            },
            'last_updated': max([task.updated_at for task in self.tasks]).isoformat() if self.tasks else None,
            'output_directory': str(self.output_dir)
        }

# CLI Interface
def main():
    """Main CLI interface for the agentic workflow."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agentic Workflow for Factual Reel Generation and Instagram Posting")
    parser.add_argument("--config", required=True, help="Path to workflow configuration file")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add URLs command
    add_parser = subparsers.add_parser('add', help='Add reel URLs to processing queue')
    add_group = add_parser.add_mutually_exclusive_group(required=True)
    add_group.add_argument('--urls', nargs='+', help='List of reel URLs')
    add_group.add_argument('--file', help='File containing reel URLs (one per line)')
    
    # Run workflow command
    run_parser = subparsers.add_parser('run', help='Run the workflow for all pending tasks')
    run_parser.add_argument('--concurrent', type=int, help='Maximum concurrent tasks')
    run_parser.add_argument('--no-auto-post', action='store_true', help='Disable auto-posting to Instagram')
    
    # Status command
    subparsers.add_parser('status', help='Get workflow status')
    
    # Create config command
    config_parser = subparsers.add_parser('create-config', help='Create example configuration file')
    config_parser.add_argument('--output', default='workflow_config.json', help='Output configuration file path')
    
    args = parser.parse_args()
    
    if args.command == 'create-config':
        # Create example configuration
        example_config = WorkflowConfig(
            factual_config_path="MVP/factual/config.json",
            instagram_access_token="YOUR_INSTAGRAM_ACCESS_TOKEN",
            instagram_business_user_id="YOUR_BUSINESS_USER_ID",
            file_upload_config={
                "type": "cloudinary",
                "cloud_name": "YOUR_CLOUDINARY_CLOUD_NAME",
                "api_key": "YOUR_CLOUDINARY_API_KEY",
                "api_secret": "YOUR_CLOUDINARY_API_SECRET"
            },
            max_concurrent_tasks=2,
            enable_auto_posting=False,
            posting_delay_minutes=30,
            min_intervention_count=1,
            max_video_duration_seconds=180,
            workflow_output_dir="workflow_output",
            keep_intermediate_files=True,
            enable_webhook_notifications=False,
            webhook_url=""
        )
        
        example_config.save_to_file(args.output)
        print(f"Example configuration created: {args.output}")
        print("Please edit the file to add your API credentials and adjust settings.")
        return
    
    # Load configuration
    try:
        config = WorkflowConfig.from_file(args.config)
    except FileNotFoundError:
        print(f"Configuration file not found: {args.config}")
        print("Create one using: python agentic_workflow.py create-config")
        sys.exit(1)
    
    # Initialize workflow
    workflow = AgenticWorkflow(config)
    
    if args.command == 'add':
        if args.urls:
            task_ids = workflow.add_reel_urls(args.urls)
        else:
            task_ids = workflow.add_reel_urls_from_file(args.file)
        
        print(f"Added {len(task_ids)} tasks to the workflow")
        for task_id in task_ids:
            print(f"  Task ID: {task_id}")
    
    elif args.command == 'run':
        # Override auto-posting if specified
        if args.no_auto_post:
            config.enable_auto_posting = False
        
        # Run the workflow
        async def run_workflow():
            summary = await workflow.run_workflow(args.concurrent)
            
            print("\nWorkflow Execution Summary:")
            print(f"Total tasks: {summary['total_tasks']}")
            print(f"Success rate: {summary['success_rate']:.1%}")
            print("\nStatus breakdown:")
            for status, count in summary['status_breakdown'].items():
                print(f"  {status}: {count}")
            
            if summary['failed_tasks']:
                print(f"\nFailed tasks:")
                for failed in summary['failed_tasks']:
                    print(f"  {failed['url']}: {failed['error']}")
            
            print(f"\nOutput directory: {summary['output_directory']}")
        
        # Run the async workflow
        asyncio.run(run_workflow())
    
    elif args.command == 'status':
        status = workflow.get_status()
        
        print(f"Workflow ID: {status['workflow_id']}")
        print(f"Total tasks: {status['total_tasks']}")
        print("\nTasks by status:")
        for status_name, count in status['tasks_by_status'].items():
            if count > 0:
                print(f"  {status_name}: {count}")
        
        if status['last_updated']:
            print(f"\nLast updated: {status['last_updated']}")
        print(f"Output directory: {status['output_directory']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()