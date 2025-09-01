#!/usr/bin/env python3
"""
Engagement Metrics Tracker for Factual Pipeline

Collects and tracks engagement metrics for processed reels including views, likes, 
comments, shares, creator info, and collaborators.
"""

import json
import csv
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


class EngagementTracker:
    """Track engagement metrics for processed reels"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.yt_dlp_path = config.get('yt_dlp_path', 'yt-dlp')
        
    def collect_metrics(self, url: str) -> Dict[str, Any]:
        """
        Collect engagement data at processing time
        
        Args:
            url: URL of the reel to analyze
            
        Returns:
            Dictionary containing engagement metrics and creator info
        """
        logger.info(f"Collecting engagement metrics for: {url}")
        
        try:
            # Get metadata using yt-dlp
            metadata = self._get_reel_metadata(url)
            
            # Extract platform-specific metrics
            platform = self._detect_platform(url)
            
            metrics = {
                'url': url,
                'platform': platform,
                'processed_at': datetime.now().isoformat(),
                'reel_id': self._extract_reel_id(url),
                'metrics': self._extract_metrics(metadata, platform),
                'creator': self._extract_creator_info(metadata, platform),
                'collaborators': self._extract_collaborators(metadata, platform),
                'content': self._extract_content_info(metadata, platform),
                'hashtags': self._extract_hashtags(metadata.get('description', '')),
                'mentions': self._extract_mentions(metadata.get('description', '')),
                'raw_metadata': metadata if self.config.get('save_raw_metadata', False) else None
            }
            
            logger.info(f"Successfully collected metrics for {platform} reel")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect metrics for {url}: {str(e)}")
            return self._create_fallback_metrics(url, str(e))
    
    def _get_reel_metadata(self, url: str) -> Dict[str, Any]:
        """Get metadata using yt-dlp"""
        
        cmd = [
            self.yt_dlp_path,
            '--dump-json',
            '--no-download',
            '--no-warnings',
            url
        ]
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=30
            )
            
            return json.loads(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while fetching metadata for {url}")
            raise Exception("Metadata fetch timeout")
        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp failed for {url}: {e.stderr}")
            raise Exception(f"yt-dlp error: {e.stderr}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON for {url}: {str(e)}")
            raise Exception("Invalid metadata format")
    
    def _extract_metrics(self, metadata: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract engagement metrics from metadata"""
        
        metrics = {
            'views': self._safe_int(metadata.get('view_count', 0)),
            'likes': self._safe_int(metadata.get('like_count', 0)),
            'comments': self._safe_int(metadata.get('comment_count', 0)),
            'shares': self._safe_int(metadata.get('repost_count', 0)),
            'duration_seconds': self._safe_float(metadata.get('duration', 0)),
            'upload_date': metadata.get('upload_date'),
            'availability': metadata.get('availability', 'public')
        }
        
        # Platform-specific metrics
        if platform == 'instagram':
            metrics.update({
                'saves': self._safe_int(metadata.get('save_count', 0)),
                'plays': self._safe_int(metadata.get('play_count', 0))
            })
        elif platform == 'facebook':
            metrics.update({
                'reactions': self._safe_int(metadata.get('reaction_count', 0)),
                'angry_reactions': self._safe_int(metadata.get('angry_count', 0)),
                'love_reactions': self._safe_int(metadata.get('love_count', 0))
            })
        
        # Calculate engagement rate if possible
        if metrics['views'] > 0:
            total_engagement = metrics['likes'] + metrics['comments'] + metrics['shares']
            metrics['engagement_rate'] = round((total_engagement / metrics['views']) * 100, 2)
        else:
            metrics['engagement_rate'] = 0
        
        return metrics
    
    def _extract_creator_info(self, metadata: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract creator information from metadata"""
        
        creator = {
            'username': metadata.get('uploader', ''),
            'display_name': metadata.get('uploader_id', ''),
            'handle': self._clean_handle(metadata.get('uploader_id', '')),
            'verified': metadata.get('verified', False),
            'follower_count': self._safe_int(metadata.get('uploader_follower_count', 0)),
            'profile_url': metadata.get('uploader_url', ''),
            'avatar_url': metadata.get('uploader_avatar_url', '')
        }
        
        # Platform-specific creator info
        if platform == 'instagram':
            creator.update({
                'is_business': metadata.get('is_business_account', False),
                'category': metadata.get('business_category', '')
            })
        
        return creator
    
    def _extract_collaborators(self, metadata: Dict[str, Any], platform: str) -> List[Dict[str, Any]]:
        """Extract collaborator information from metadata"""
        
        collaborators = []
        
        # Look for collaborators in various metadata fields
        collab_fields = [
            'collaborators',
            'tagged_users',
            'mentioned_users',
            'featured_users'
        ]
        
        for field in collab_fields:
            if field in metadata and isinstance(metadata[field], list):
                for collab in metadata[field]:
                    if isinstance(collab, dict):
                        collaborators.append({
                            'username': collab.get('username', ''),
                            'display_name': collab.get('display_name', ''),
                            'handle': self._clean_handle(collab.get('username', '')),
                            'verified': collab.get('verified', False),
                            'role': collab.get('role', 'collaborator')
                        })
        
        # Also extract from description mentions
        description = metadata.get('description', '')
        mentions = self._extract_mentions(description)
        
        for mention in mentions:
            # Avoid duplicates
            if not any(collab['handle'] == mention for collab in collaborators):
                collaborators.append({
                    'username': mention,
                    'display_name': mention,
                    'handle': mention,
                    'verified': False,
                    'role': 'mentioned'
                })
        
        return collaborators
    
    def _extract_content_info(self, metadata: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Extract content-related information"""
        
        content = {
            'title': metadata.get('title', ''),
            'description': metadata.get('description', ''),
            'thumbnail_url': metadata.get('thumbnail', ''),
            'width': self._safe_int(metadata.get('width', 0)),
            'height': self._safe_int(metadata.get('height', 0)),
            'fps': self._safe_float(metadata.get('fps', 0)),
            'format': metadata.get('ext', ''),
            'filesize': self._safe_int(metadata.get('filesize', 0))
        }
        
        # Extract audio info if available
        if 'audio_codec' in metadata:
            content['audio_codec'] = metadata['audio_codec']
        if 'video_codec' in metadata:
            content['video_codec'] = metadata['video_codec']
        
        return content
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        
        if not text:
            return []
        
        # Find hashtags (# followed by alphanumeric characters and underscores)
        hashtag_pattern = r'#([a-zA-Z0-9_]+)'
        hashtags = re.findall(hashtag_pattern, text)
        
        # Clean and deduplicate
        hashtags = [tag.lower() for tag in hashtags if len(tag) > 1]
        return list(set(hashtags))
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from text"""
        
        if not text:
            return []
        
        # Find mentions (@ followed by alphanumeric characters and underscores)
        mention_pattern = r'@([a-zA-Z0-9_.]+)'
        mentions = re.findall(mention_pattern, text)
        
        # Clean and deduplicate
        mentions = [mention.lower() for mention in mentions if len(mention) > 1]
        return list(set(mentions))
    
    def _extract_reel_id(self, url: str) -> str:
        """Extract reel ID from URL"""
        
        if 'instagram.com' in url:
            # Instagram: /reel/ABC123/ or /p/ABC123/
            match = re.search(r'/(reel|p)/([^/?]+)', url)
            if match:
                return match.group(2)
        elif 'facebook.com' in url:
            # Facebook: various formats
            if 'watch?v=' in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'v' in params:
                    return params['v'][0]
            elif '/videos/' in url:
                match = re.search(r'/videos/(\d+)', url)
                if match:
                    return match.group(1)
        
        # Fallback: use last part of path
        path_parts = urlparse(url).path.strip('/').split('/')
        return path_parts[-1] if path_parts else 'unknown'
    
    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL"""
        
        if 'instagram.com' in url:
            return 'instagram'
        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'
        else:
            return 'unknown'
    
    def _clean_handle(self, handle: str) -> str:
        """Clean and normalize handle"""
        
        if not handle:
            return ''
        
        # Remove @ if present
        handle = handle.lstrip('@')
        
        # Keep only alphanumeric, dots, and underscores
        handle = re.sub(r'[^a-zA-Z0-9._]', '', handle)
        
        return handle.lower()
    
    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int"""
        
        if value is None:
            return 0
        
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return 0
    
    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float"""
        
        if value is None:
            return 0.0
        
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return 0.0
    
    def _create_fallback_metrics(self, url: str, error: str) -> Dict[str, Any]:
        """Create fallback metrics when collection fails"""
        
        return {
            'url': url,
            'platform': self._detect_platform(url),
            'processed_at': datetime.now().isoformat(),
            'reel_id': self._extract_reel_id(url),
            'error': error,
            'metrics': {
                'views': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'duration_seconds': 0,
                'engagement_rate': 0
            },
            'creator': {
                'username': '',
                'display_name': '',
                'handle': '',
                'verified': False,
                'follower_count': 0
            },
            'collaborators': [],
            'content': {},
            'hashtags': [],
            'mentions': []
        }
    
    def save_metrics(self, metrics: Dict[str, Any], output_path: str) -> None:
        """
        Save metrics to JSON file
        
        Args:
            metrics: Metrics dictionary to save
            output_path: Path where to save the metrics
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved metrics to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics to {output_path}: {str(e)}")
    
    def save_batch_metrics_csv(self, batch_metrics: List[Dict[str, Any]], output_path: str) -> None:
        """
        Save batch metrics to CSV file
        
        Args:
            batch_metrics: List of metrics dictionaries
            output_path: Path where to save the CSV
        """
        if not batch_metrics:
            logger.warning("No metrics to save to CSV")
            return
        
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Define CSV columns
            fieldnames = [
                'url', 'platform', 'reel_id', 'processed_at',
                'creator_username', 'creator_handle', 'creator_verified', 'creator_followers',
                'views', 'likes', 'comments', 'shares', 'engagement_rate',
                'duration_seconds', 'hashtags_count', 'mentions_count', 'collaborators_count',
                'title', 'error'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for metrics in batch_metrics:
                    # Flatten metrics for CSV
                    row = {
                        'url': metrics.get('url', ''),
                        'platform': metrics.get('platform', ''),
                        'reel_id': metrics.get('reel_id', ''),
                        'processed_at': metrics.get('processed_at', ''),
                        'creator_username': metrics.get('creator', {}).get('username', ''),
                        'creator_handle': metrics.get('creator', {}).get('handle', ''),
                        'creator_verified': metrics.get('creator', {}).get('verified', False),
                        'creator_followers': metrics.get('creator', {}).get('follower_count', 0),
                        'views': metrics.get('metrics', {}).get('views', 0),
                        'likes': metrics.get('metrics', {}).get('likes', 0),
                        'comments': metrics.get('metrics', {}).get('comments', 0),
                        'shares': metrics.get('metrics', {}).get('shares', 0),
                        'engagement_rate': metrics.get('metrics', {}).get('engagement_rate', 0),
                        'duration_seconds': metrics.get('metrics', {}).get('duration_seconds', 0),
                        'hashtags_count': len(metrics.get('hashtags', [])),
                        'mentions_count': len(metrics.get('mentions', [])),
                        'collaborators_count': len(metrics.get('collaborators', [])),
                        'title': metrics.get('content', {}).get('title', ''),
                        'error': metrics.get('error', '')
                    }
                    
                    writer.writerow(row)
            
            logger.info(f"Saved batch metrics CSV to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save batch metrics CSV to {output_path}: {str(e)}")
    
    def generate_metrics_summary(self, batch_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for batch metrics
        
        Args:
            batch_metrics: List of metrics dictionaries
            
        Returns:
            Dictionary with summary statistics
        """
        if not batch_metrics:
            return {}
        
        # Filter out failed metrics
        valid_metrics = [m for m in batch_metrics if 'error' not in m]
        
        if not valid_metrics:
            return {'error': 'No valid metrics found'}
        
        # Calculate aggregates
        total_views = sum(m.get('metrics', {}).get('views', 0) for m in valid_metrics)
        total_likes = sum(m.get('metrics', {}).get('likes', 0) for m in valid_metrics)
        total_comments = sum(m.get('metrics', {}).get('comments', 0) for m in valid_metrics)
        total_shares = sum(m.get('metrics', {}).get('shares', 0) for m in valid_metrics)
        
        engagement_rates = [m.get('metrics', {}).get('engagement_rate', 0) for m in valid_metrics]
        avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0
        
        # Platform breakdown
        platforms = {}
        for metrics in valid_metrics:
            platform = metrics.get('platform', 'unknown')
            platforms[platform] = platforms.get(platform, 0) + 1
        
        # Creator analysis
        creators = {}
        for metrics in valid_metrics:
            creator = metrics.get('creator', {}).get('handle', 'unknown')
            if creator not in creators:
                creators[creator] = {
                    'count': 0,
                    'total_views': 0,
                    'verified': metrics.get('creator', {}).get('verified', False)
                }
            creators[creator]['count'] += 1
            creators[creator]['total_views'] += metrics.get('metrics', {}).get('views', 0)
        
        return {
            'total_reels': len(valid_metrics),
            'failed_reels': len(batch_metrics) - len(valid_metrics),
            'totals': {
                'views': total_views,
                'likes': total_likes,
                'comments': total_comments,
                'shares': total_shares
            },
            'averages': {
                'views_per_reel': total_views / len(valid_metrics) if valid_metrics else 0,
                'likes_per_reel': total_likes / len(valid_metrics) if valid_metrics else 0,
                'engagement_rate': round(avg_engagement_rate, 2)
            },
            'platforms': platforms,
            'top_creators': dict(sorted(creators.items(), 
                                      key=lambda x: x[1]['total_views'], 
                                      reverse=True)[:5])
        }
