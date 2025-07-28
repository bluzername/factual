#!/usr/bin/env python3
"""
File Uploader Utility for Instagram Publishing

Handles uploading video and image files to cloud storage services
to make them publicly accessible for Instagram Graph API.
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path
import requests
import time

logger = logging.getLogger(__name__)

class FileUploader(ABC):
    """Abstract base class for file uploaders."""
    
    @abstractmethod
    def upload_file(self, file_path: str, content_type: str) -> str:
        """Upload a file and return the public URL.
        
        Args:
            file_path: Path to the file to upload
            content_type: MIME type of the file
            
        Returns:
            Public URL of the uploaded file
        """
        pass

class CloudinaryUploader(FileUploader):
    """Cloudinary file uploader implementation."""
    
    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        """Initialize Cloudinary uploader.
        
        Args:
            cloud_name: Cloudinary cloud name
            api_key: Cloudinary API key
            api_secret: Cloudinary API secret
        """
        self.cloud_name = cloud_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = f"https://api.cloudinary.com/v1_1/{cloud_name}"
        
    def upload_file(self, file_path: str, content_type: str) -> str:
        """Upload file to Cloudinary."""
        try:
            import cloudinary
            import cloudinary.uploader
            
            # Configure Cloudinary
            cloudinary.config(
                cloud_name=self.cloud_name,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Determine resource type
            resource_type = "video" if content_type.startswith("video/") else "image"
            
            # Upload file
            result = cloudinary.uploader.upload(
                file_path,
                resource_type=resource_type,
                use_filename=True,
                unique_filename=True
            )
            
            logger.info(f"Successfully uploaded {file_path} to Cloudinary: {result['secure_url']}")
            return result['secure_url']
            
        except ImportError:
            raise Exception("Cloudinary package not installed. Install with: pip install cloudinary")
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            raise

class S3Uploader(FileUploader):
    """AWS S3 file uploader implementation."""
    
    def __init__(self, bucket_name: str, region: str, access_key_id: str, secret_access_key: str):
        """Initialize S3 uploader.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
        """
        self.bucket_name = bucket_name
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        
    def upload_file(self, file_path: str, content_type: str) -> str:
        """Upload file to S3."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key
            )
            
            # Generate unique filename
            filename = f"factual_reels/{Path(file_path).stem}_{int(time.time())}{Path(file_path).suffix}"
            
            # Upload file
            s3_client.upload_file(
                file_path,
                self.bucket_name,
                filename,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'public-read'
                }
            )
            
            # Generate public URL
            public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{filename}"
            
            logger.info(f"Successfully uploaded {file_path} to S3: {public_url}")
            return public_url
            
        except ImportError:
            raise Exception("boto3 package not installed. Install with: pip install boto3")
        except ClientError as e:
            logger.error(f"S3 upload failed: {str(e)}")
            raise

class FileShareUploader(FileUploader):
    """Simple file sharing service uploader (using file.io or similar)."""
    
    def __init__(self, service_url: str = "https://file.io"):
        """Initialize file sharing uploader.
        
        Args:
            service_url: Base URL of the file sharing service
        """
        self.service_url = service_url
        
    def upload_file(self, file_path: str, content_type: str) -> str:
        """Upload file to file sharing service."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, content_type)}
                response = requests.post(self.service_url, files=files)
                
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    public_url = result.get('link')
                    logger.info(f"Successfully uploaded {file_path} to {self.service_url}: {public_url}")
                    return public_url
                else:
                    raise Exception(f"Upload failed: {result.get('message', 'Unknown error')}")
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.error(f"File sharing upload failed: {str(e)}")
            raise

def create_uploader(config: Dict[str, Any]) -> FileUploader:
    """Create a file uploader based on configuration.
    
    Args:
        config: Upload configuration dictionary
        
    Returns:
        Configured file uploader instance
    """
    uploader_type = config.get('type', '').lower()
    
    if uploader_type == 'cloudinary':
        return CloudinaryUploader(
            cloud_name=config['cloud_name'],
            api_key=config['api_key'],
            api_secret=config['api_secret']
        )
    elif uploader_type == 's3':
        return S3Uploader(
            bucket_name=config['bucket_name'],
            region=config['region'],
            access_key_id=config['access_key_id'],
            secret_access_key=config['secret_access_key']
        )
    elif uploader_type == 'fileshare':
        return FileShareUploader(
            service_url=config.get('service_url', 'https://file.io')
        )
    else:
        raise ValueError(f"Unsupported uploader type: {uploader_type}")