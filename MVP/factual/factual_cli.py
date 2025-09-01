#!/usr/bin/env python3
"""
Command Line Interface for Factual Pipeline v2.0

Provides a clean CLI interface using the unified processor with proper session
isolation, HTML summaries, and engagement metrics.
"""

import argparse
import sys
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from unified_processor import FactualProcessor

def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main CLI entry point"""
    
    parser = argparse.ArgumentParser(
        description="Factual Pipeline v2.0 - AI-powered fact-checking for social media reels",
        epilog="""
Examples:
  %(prog)s https://www.instagram.com/reel/ABC123/
  %(prog)s --batch urls.txt
  %(prog)s --batch urls.txt --config custom_config.json
  %(prog)s --verbose https://www.instagram.com/reel/ABC123/
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Input source (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "url", 
        nargs='?', 
        help="URL of the Instagram or Facebook reel to process"
    )
    input_group.add_argument(
        "--batch", 
        help="Path to text file containing URLs (one per line) for batch processing"
    )
    
    # Optional arguments
    parser.add_argument(
        "--config", 
        help="Path to configuration file (JSON format)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose logging output"
    )
    parser.add_argument(
        "--mode",
        choices=["single", "batch", "auto"],
        default="auto",
        help="Processing mode (default: auto-detect)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Initialize processor
        print("🚀 Initializing Factual Pipeline v2.0...")
        processor = FactualProcessor(args.config)
        
        # Determine input source and mode
        if args.batch:
            input_source = args.batch
            mode = "batch"
        else:
            input_source = args.url
            mode = "single"
        
        # Override mode if specified
        if args.mode != "auto":
            mode = args.mode
        
        print(f"📋 Mode: {mode.upper()}")
        print(f"🎯 Input: {input_source}")
        print("")
        
        # Process
        results = processor.process(input_source, mode=mode)
        
        # Display results
        if mode == "single":
            _display_single_results(results)
        else:
            _display_batch_results(results)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Processing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

def _display_single_results(results: dict):
    """Display results for single reel processing"""
    
    if results.get('status') == 'failed':
        print(f"❌ Processing failed: {results.get('error', 'Unknown error')}")
        return
    
    print("✅ Processing completed successfully!")
    print("")
    print(f"📁 Output Directory: {results.get('output_directory', 'Unknown')}")
    print("")
    print("📄 Generated Files:")
    
    files = [
        ('🎥 Video', results.get('output_video')),
        ('📄 HTML Summary', results.get('html_summary')),
        ('📱 Instagram Description', results.get('instagram_description')),
        ('📚 Sources (Copyable)', results.get('sources_text')),
        ('📊 Engagement Metrics', results.get('metrics_file')),
        ('📋 Manifest', results.get('manifest')),
        ('🖼️  Summary Slide', results.get('summary_slide'))
    ]
    
    for label, path in files:
        if path:
            print(f"  {label}: {path}")
    
    # Display metrics summary if available
    if results.get('metrics'):
        metrics = results['metrics']['metrics']
        print("")
        print("📊 Engagement Snapshot:")
        print(f"  👀 Views: {metrics.get('views', 0):,}")
        print(f"  ❤️  Likes: {metrics.get('likes', 0):,}")
        print(f"  💬 Comments: {metrics.get('comments', 0):,}")
        print(f"  🔄 Shares: {metrics.get('shares', 0):,}")
        print(f"  📈 Engagement Rate: {metrics.get('engagement_rate', 0)}%")
    
    print("")
    print("🎯 Next Steps:")
    print("  1. Review the HTML summary for detailed analysis")
    print("  2. Copy the Instagram description for posting")
    print("  3. Use the sources text for fact-check transparency")

def _display_batch_results(results: dict):
    """Display results for batch processing"""
    
    if results.get('status') == 'failed':
        print(f"❌ Batch processing failed: {results.get('error', 'Unknown error')}")
        return
    
    total = results.get('total_urls', 0)
    successful = results.get('successful', 0)
    failed = results.get('failed', 0)
    success_rate = (successful / total * 100) if total > 0 else 0
    
    print("✅ Batch processing completed!")
    print("")
    print("📊 Summary:")
    print(f"  📁 Total URLs: {total}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📈 Success Rate: {success_rate:.1f}%")
    print("")
    print(f"📁 Output Directory: {results.get('batch_output_dir', 'Unknown')}")
    print("")
    print("📄 Batch Reports:")
    
    reports = [
        ('📊 HTML Summary', results.get('batch_html_summary')),
        ('📈 Metrics CSV', results.get('batch_metrics_csv')),
        ('📋 JSON Summary', results.get('batch_output_dir', '') + '/batch_summary.json'),
        ('📝 Text Summary', results.get('batch_text_summary')),
        ('📊 Metrics Summary', results.get('metrics_summary'))
    ]
    
    for label, path in reports:
        if path:
            print(f"  {label}: {path}")
    
    if failed > 0:
        print("")
        print("❌ Failed URLs:")
        for failed_url in results.get('failed_urls', []):
            print(f"  Line {failed_url.get('line_number', '?')}: {failed_url.get('url', 'Unknown')}")
            print(f"    Error: {failed_url.get('error', 'Unknown error')}")
    
    print("")
    print("🎯 Next Steps:")
    print("  1. Open the HTML summary for a visual overview")
    print("  2. Check individual reel directories for detailed outputs")
    print("  3. Use the metrics CSV for engagement analysis")

if __name__ == "__main__":
    sys.exit(main())
