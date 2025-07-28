#!/usr/bin/env python3
"""
Example Batch Runner for Agentic Workflow

This script demonstrates how to use the agentic workflow programmatically
to process a batch of reels from various sources.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List
import logging

# Import the workflow components
from agentic_workflow import AgenticWorkflow, WorkflowConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FactualReelBatchProcessor:
    """Example batch processor for factual reels."""
    
    def __init__(self, config_path: str):
        """Initialize with workflow configuration.
        
        Args:
            config_path: Path to workflow configuration file
        """
        self.config = WorkflowConfig.from_file(config_path)
        self.workflow = AgenticWorkflow(self.config)
        
    async def process_trending_reels(self, hashtags: List[str], max_reels_per_hashtag: int = 5):
        """Process trending reels from specified hashtags.
        
        Args:
            hashtags: List of hashtags to search for trending reels
            max_reels_per_hashtag: Maximum reels to process per hashtag
        """
        logger.info(f"Processing trending reels from hashtags: {hashtags}")
        
        # This is a placeholder - in a real implementation, you would:
        # 1. Use the Instagram Graph API to find trending reels
        # 2. Filter for reels that might contain factual claims
        # 3. Add them to the workflow
        
        example_urls = [
            "https://www.instagram.com/reel/DE_C78HyOVM/",  # Example working URL from the existing pipeline
            # Add more URLs here based on your trending analysis
        ]
        
        # Add URLs to workflow
        task_ids = self.workflow.add_reel_urls(example_urls)
        logger.info(f"Added {len(task_ids)} reels to processing queue")
        
        # Run the workflow
        summary = await self.workflow.run_workflow()
        
        return summary
    
    async def process_curated_list(self, reel_urls: List[str]):
        """Process a curated list of reel URLs.
        
        Args:
            reel_urls: List of reel URLs to process
        """
        logger.info(f"Processing {len(reel_urls)} curated reels")
        
        # Add URLs to workflow
        task_ids = self.workflow.add_reel_urls(reel_urls)
        
        # Run the workflow
        summary = await self.workflow.run_workflow()
        
        return summary
    
    async def process_from_file(self, file_path: str):
        """Process reels from a file containing URLs.
        
        Args:
            file_path: Path to file with URLs (one per line)
        """
        logger.info(f"Processing reels from file: {file_path}")
        
        # Add URLs from file
        task_ids = self.workflow.add_reel_urls_from_file(file_path)
        
        # Run the workflow
        summary = await self.workflow.run_workflow()
        
        return summary
    
    def get_status_report(self) -> dict:
        """Get current workflow status."""
        return self.workflow.get_status()

async def main():
    """Main example runner."""
    
    # Check if configuration file exists
    config_path = "workflow_config.json"
    if not Path(config_path).exists():
        print(f"Configuration file not found: {config_path}")
        print("Create one using: python agentic_workflow.py create-config")
        return
    
    try:
        # Initialize batch processor
        processor = FactualReelBatchProcessor(config_path)
        
        # Example 1: Process a curated list of reels
        print("=" * 60)
        print("Example 1: Processing curated list of reels")
        print("=" * 60)
        
        curated_reels = [
            "https://www.instagram.com/reel/DE_C78HyOVM/",  # Working example URL
            # Add more URLs here
        ]
        
        summary = await processor.process_curated_list(curated_reels)
        
        print(f"\nCurated List Processing Summary:")
        print(f"Total tasks: {summary['total_tasks']}")
        print(f"Success rate: {summary['success_rate']:.1%}")
        print(f"Status breakdown: {summary['status_breakdown']}")
        
        if summary['failed_tasks']:
            print(f"\nFailed tasks:")
            for failed in summary['failed_tasks']:
                print(f"  {failed['url']}: {failed['error']}")
        
        # Example 2: Process from file (if available)
        urls_file = "example_reel_urls.txt"
        if Path(urls_file).exists():
            print("\n" + "=" * 60)
            print("Example 2: Processing reels from file")
            print("=" * 60)
            
            summary = await processor.process_from_file(urls_file)
            
            print(f"\nFile Processing Summary:")
            print(f"Total tasks: {summary['total_tasks']}")
            print(f"Success rate: {summary['success_rate']:.1%}")
        
        # Example 3: Status monitoring
        print("\n" + "=" * 60)
        print("Example 3: Current workflow status")
        print("=" * 60)
        
        status = processor.get_status_report()
        print(f"Workflow ID: {status['workflow_id']}")
        print(f"Total tasks: {status['total_tasks']}")
        print(f"Tasks by status: {status['tasks_by_status']}")
        print(f"Output directory: {status['output_directory']}")
        
    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        return

def create_example_urls_file():
    """Create an example URLs file for testing."""
    urls = [
        "# Example reel URLs for factual processing",
        "# Add one URL per line, comments start with #",
        "",
        "https://www.instagram.com/reel/DE_C78HyOVM/",
        "# Add more Instagram reel URLs here",
        "# https://www.instagram.com/reel/EXAMPLE2/",
        "# https://www.facebook.com/watch?v=EXAMPLE3",
    ]
    
    with open("example_reel_urls.txt", "w") as f:
        f.write("\n".join(urls))
    
    print("Created example_reel_urls.txt - add your reel URLs to this file")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Example batch runner for agentic workflow")
    parser.add_argument("--create-example-file", action="store_true", 
                       help="Create example URLs file")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be processed without actually running")
    
    args = parser.parse_args()
    
    if args.create_example_file:
        create_example_urls_file()
        sys.exit(0)
    
    if args.dry_run:
        print("DRY RUN MODE - Would process reels but auto-posting is disabled")
        # You could modify the config here to ensure no posting happens
    
    # Run the main example
    asyncio.run(main())