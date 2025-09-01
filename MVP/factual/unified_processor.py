#!/usr/bin/env python3
"""
Unified Processor for Factual Pipeline

Provides a clean interface for both single and batch processing with proper
session isolation, HTML generation, and metrics tracking.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Union, Optional

try:
    from .factual_pipeline import FactualPipeline
    from .html_summary_generator import HTMLSummaryGenerator
    from .engagement_tracker import EngagementTracker
except ImportError:
    # Handle relative import when running as script
    from factual_pipeline import FactualPipeline
    from html_summary_generator import HTMLSummaryGenerator
    from engagement_tracker import EngagementTracker

logger = logging.getLogger(__name__)


class FactualProcessor:
    """Unified processor for single and batch operations"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the unified processor
        
        Args:
            config_path: Optional path to configuration file
        """
        # Create core pipeline instance
        self.pipeline = FactualPipeline(config_path)
        self.config = self.pipeline.config
        
        # Initialize HTML generator and metrics tracker
        self.html_generator = HTMLSummaryGenerator(self.config)
        self.engagement_tracker = EngagementTracker(self.config)
        
        logger.info("Unified Factual Processor initialized")
    
    def process(self, input_source: Union[str, List[str]], mode: str = "auto") -> Dict[str, Any]:
        """
        Process reels in single or batch mode
        
        Args:
            input_source: URL string, list of URLs, or path to batch file
            mode: "single", "batch", or "auto" (detect from input)
            
        Returns:
            Dictionary with processing results
        """
        if mode == "auto":
            mode = self._detect_mode(input_source)
        
        logger.info(f"Starting {mode} processing")
        
        if mode == "single":
            return self._process_single(input_source)
        else:
            return self._process_batch(input_source)
    
    def _detect_mode(self, input_source: Union[str, List[str]]) -> str:
        """Detect processing mode from input"""
        
        if isinstance(input_source, list):
            return "batch"
        elif isinstance(input_source, str):
            # Check if it's a URL or file path
            if input_source.startswith(('http://', 'https://')):
                return "single"
            elif os.path.isfile(input_source):
                return "batch"
            else:
                # Assume it's a URL if it contains common social media domains
                if any(domain in input_source for domain in ['instagram.com', 'facebook.com', 'fb.watch']):
                    return "single"
                else:
                    return "batch"  # Assume batch file
        
        return "single"
    
    def _process_single(self, url: str) -> Dict[str, Any]:
        """
        Process a single reel with full feature set
        
        Args:
            url: URL of the reel to process
            
        Returns:
            Dictionary with processing results and generated files
        """
        logger.info(f"Processing single reel: {url}")
        
        try:
            # Generate unique session ID for this reel
            session_id = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Create output directory
            output_dir = Path(self.config['output_dir']) / session_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process the reel with session isolation
            reel_result = self._process_reel_with_session(url, session_id)
            
            # Collect engagement metrics
            logger.info("Collecting engagement metrics...")
            try:
                metrics = self.engagement_tracker.collect_metrics(url)
                metrics_path = str(output_dir / "metrics.json")
                self.engagement_tracker.save_metrics(metrics, metrics_path)
                reel_result['metrics_file'] = metrics_path
                reel_result['metrics'] = metrics
            except Exception as e:
                logger.warning(f"Failed to collect metrics: {str(e)}")
                reel_result['metrics_error'] = str(e)
            
            # Generate HTML summaries
            logger.info("Generating HTML summaries...")
            try:
                # Add original URL to result for HTML generation
                reel_result['original_url'] = url
                
                html_files = self.html_generator.generate_summary(reel_result, str(output_dir))
                reel_result.update(html_files)
            except Exception as e:
                logger.warning(f"Failed to generate HTML summaries: {str(e)}")
                reel_result['html_error'] = str(e)
            
            # Add processing metadata
            reel_result.update({
                'session_id': session_id,
                'output_directory': str(output_dir),
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'single'
            })
            
            logger.info(f"Successfully processed single reel: {url}")
            return reel_result
            
        except Exception as e:
            logger.error(f"Failed to process single reel {url}: {str(e)}")
            return {
                'url': url,
                'status': 'failed',
                'error': str(e),
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'single'
            }
    
    def _process_batch(self, input_source: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Process multiple reels with proper isolation
        
        Args:
            input_source: Path to batch file or list of URLs
            
        Returns:
            Dictionary with batch processing results
        """
        logger.info(f"Processing batch: {input_source}")
        
        try:
            # Parse URLs
            if isinstance(input_source, list):
                urls = [(i+1, url) for i, url in enumerate(input_source)]
                batch_source = "URL list"
            else:
                urls = self._read_batch_file(input_source)
                batch_source = input_source
            
            if not urls:
                raise ValueError(f"No URLs found in batch source: {batch_source}")
            
            # Create batch output directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_output_dir = Path(self.config['output_dir']) / f"batch_{timestamp}"
            batch_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize results tracking
            results = {
                'batch_source': batch_source,
                'total_urls': len(urls),
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'batch_output_dir': str(batch_output_dir),
                'results': [],
                'failed_urls': [],
                'batch_metrics': [],
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'batch'
            }
            
            logger.info(f"Processing {len(urls)} URLs in batch mode")
            
            # Process each URL with isolation
            for line_num, url in urls:
                logger.info(f"Processing URL {results['processed'] + 1}/{len(urls)} (line {line_num}): {url}")
                
                try:
                    # Generate unique session ID for this reel
                    reel_session_id = f"{timestamp}_{line_num:03d}"
                    
                    # Create individual output directory
                    url_safe = self._make_url_safe(url)
                    reel_output_dir = batch_output_dir / f"{line_num:03d}_{url_safe}"
                    reel_output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Process the reel
                    reel_result = self._process_reel_with_session(url, reel_session_id, str(reel_output_dir))
                    
                    # Collect engagement metrics
                    try:
                        metrics = self.engagement_tracker.collect_metrics(url)
                        metrics_path = str(reel_output_dir / "metrics.json")
                        self.engagement_tracker.save_metrics(metrics, metrics_path)
                        reel_result['metrics_file'] = metrics_path
                        reel_result['metrics'] = metrics
                        results['batch_metrics'].append(metrics)
                    except Exception as e:
                        logger.warning(f"Failed to collect metrics for {url}: {str(e)}")
                        reel_result['metrics_error'] = str(e)
                    
                    # Generate HTML summaries
                    try:
                        reel_result['original_url'] = url
                        html_files = self.html_generator.generate_summary(reel_result, str(reel_output_dir))
                        reel_result.update(html_files)
                    except Exception as e:
                        logger.warning(f"Failed to generate HTML for {url}: {str(e)}")
                        reel_result['html_error'] = str(e)
                    
                    # Add metadata
                    reel_result.update({
                        'line_number': line_num,
                        'url': url,
                        'session_id': reel_session_id,
                        'reel_output_dir': str(reel_output_dir),
                        'status': 'success'
                    })
                    
                    results['results'].append(reel_result)
                    results['successful'] += 1
                    
                    logger.info(f"Successfully processed reel {results['processed'] + 1}: {url}")
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to process reel {results['processed'] + 1} (line {line_num}): {error_msg}")
                    
                    failed_result = {
                        'line_number': line_num,
                        'url': url,
                        'status': 'failed',
                        'error': error_msg
                    }
                    
                    results['failed_urls'].append(failed_result)
                    results['failed'] += 1
                
                finally:
                    results['processed'] += 1
            
            # Generate batch summaries
            self._generate_batch_summaries(results)
            
            logger.info(f"Batch processing complete: {results['successful']}/{results['total_urls']} successful")
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}")
            return {
                'batch_source': str(input_source),
                'status': 'failed',
                'error': str(e),
                'processed_at': datetime.now().isoformat(),
                'processing_mode': 'batch'
            }
    
    def _process_reel_with_session(self, url: str, session_id: str, output_dir: str = None) -> Dict[str, Any]:
        """
        Process a single reel with proper session isolation
        
        Args:
            url: URL to process
            session_id: Unique session ID for this processing
            output_dir: Optional custom output directory
            
        Returns:
            Processing result dictionary
        """
        # Store original session ID and output dir
        original_session_id = getattr(self.pipeline, 'session_id', None)
        original_output_dir = self.pipeline.config.get('output_dir')
        
        try:
            # Set session-specific configuration
            self.pipeline.session_id = session_id
            
            if output_dir:
                self.pipeline.config['output_dir'] = output_dir
            
            # Process the reel
            result = self.pipeline.process_reel(url)
            
            return result
            
        finally:
            # Restore original configuration
            if original_session_id:
                self.pipeline.session_id = original_session_id
            if original_output_dir:
                self.pipeline.config['output_dir'] = original_output_dir
    
    def _read_batch_file(self, file_path: str) -> List[tuple]:
        """Read URLs from batch file"""
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Batch file not found: {file_path}")
        
        urls = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    urls.append((line_num, line))
        
        return urls
    
    def _make_url_safe(self, url: str) -> str:
        """Make URL safe for use in directory names"""
        
        import re
        
        # Extract meaningful part from URL
        if 'instagram.com' in url:
            match = re.search(r'/(reel|p)/([^/?]+)', url)
            if match:
                return f"ig_{match.group(2)}"
        elif 'facebook.com' in url:
            if 'watch?v=' in url:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'v' in params:
                    return f"fb_{params['v'][0]}"
        
        # Fallback: clean the URL
        safe = re.sub(r'[^\w\-_.]', '_', url.split('/')[-1] or "reel")
        return safe[:50]  # Limit length
    
    def _generate_batch_summaries(self, results: Dict[str, Any]) -> None:
        """Generate comprehensive batch summaries"""
        
        batch_output_dir = Path(results['batch_output_dir'])
        
        # Generate JSON summary
        summary_path = batch_output_dir / 'batch_summary.json'
        summary = {
            'batch_info': {
                'batch_source': results['batch_source'],
                'processed_at': results['processed_at'],
                'total_urls': results['total_urls'],
                'successful': results['successful'],
                'failed': results['failed'],
                'success_rate': f"{(results['successful'] / results['total_urls'] * 100):.1f}%" if results['total_urls'] > 0 else "0%"
            },
            'successful_results': [r for r in results['results'] if r.get('status') == 'success'],
            'failed_results': results['failed_urls']
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Generate HTML batch summary
        try:
            html_path = self.html_generator.generate_batch_summary(results, str(batch_output_dir))
            results['batch_html_summary'] = html_path
        except Exception as e:
            logger.warning(f"Failed to generate batch HTML summary: {str(e)}")
        
        # Generate metrics CSV
        if results['batch_metrics']:
            try:
                csv_path = str(batch_output_dir / 'batch_metrics.csv')
                self.engagement_tracker.save_batch_metrics_csv(results['batch_metrics'], csv_path)
                results['batch_metrics_csv'] = csv_path
                
                # Generate metrics summary
                metrics_summary = self.engagement_tracker.generate_metrics_summary(results['batch_metrics'])
                summary_path = str(batch_output_dir / 'metrics_summary.json')
                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(metrics_summary, f, indent=2, ensure_ascii=False)
                results['metrics_summary'] = summary_path
                
            except Exception as e:
                logger.warning(f"Failed to generate metrics summaries: {str(e)}")
        
        # Generate text summary
        text_summary_path = batch_output_dir / 'batch_summary.txt'
        with open(text_summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("FACTUAL BATCH PROCESSING SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Batch Source: {results['batch_source']}\n")
            f.write(f"Processed At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Output Directory: {results['batch_output_dir']}\n\n")
            
            f.write(f"RESULTS SUMMARY:\n")
            f.write(f"Total URLs: {results['total_urls']}\n")
            f.write(f"Successful: {results['successful']}\n")
            f.write(f"Failed: {results['failed']}\n")
            f.write(f"Success Rate: {(results['successful'] / results['total_urls'] * 100):.1f}%\n\n")
            
            if results['successful'] > 0:
                f.write("SUCCESSFUL PROCESSING:\n")
                for result in results['results']:
                    if result.get('status') == 'success':
                        f.write(f"✅ Line {result.get('line_number', '?')}: {result.get('url', 'Unknown URL')}\n")
                        f.write(f"   Output: {result.get('reel_output_dir', 'Unknown')}\n")
                f.write("\n")
            
            if results['failed'] > 0:
                f.write("FAILED PROCESSING:\n")
                for failed in results['failed_urls']:
                    f.write(f"❌ Line {failed.get('line_number', '?')}: {failed.get('url', 'Unknown URL')}\n")
                    f.write(f"   Error: {failed.get('error', 'Unknown error')}\n")
                f.write("\n")
            
            f.write("Generated Files:\n")
            f.write(f"- JSON Summary: batch_summary.json\n")
            if results.get('batch_html_summary'):
                f.write(f"- HTML Summary: batch_summary.html\n")
            if results.get('batch_metrics_csv'):
                f.write(f"- Metrics CSV: batch_metrics.csv\n")
            if results.get('metrics_summary'):
                f.write(f"- Metrics Summary: metrics_summary.json\n")
        
        results['batch_text_summary'] = str(text_summary_path)
