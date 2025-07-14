#!/usr/bin/env python3
"""
Test script for Factual pipeline.
Validates pipeline functionality without processing actual Instagram Reels.
"""

import os
import sys
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the pipeline module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factual_pipeline import FactualPipeline, Intervention


class TestFactualPipeline(unittest.TestCase):
    """Test cases for Factual pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "output"
        self.assets_dir = Path(self.temp_dir.name) / "assets"
        self.temp_subdir = Path(self.temp_dir.name) / "temp"
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)
        os.makedirs(self.temp_subdir, exist_ok=True)
        
        # Create a dummy watermark file
        self.watermark_path = self.assets_dir / "logo_watermark.png"
        with open(self.watermark_path, 'w') as f:
            f.write("dummy watermark file")
        
        # Configure test pipeline
        self.config = {
            "openai_api_key": "test_openai_key",
            "elevenlabs_api_key": "test_elevenlabs_key",
            "elevenlabs_voice_id": "test_voice_id",
            "whisper_model": "test_model",
            "watermark_path": str(self.watermark_path),
            "output_dir": str(self.output_dir),
            "temp_dir": str(self.temp_subdir),
            "ffmpeg_path": "echo",  # Use echo instead of real ffmpeg
            "yt_dlp_path": "echo",  # Use echo instead of real yt-dlp
            "max_retries": 1,
            "retry_delay": 0
        }
        
        # Create a test config file
        self.config_path = Path(self.temp_dir.name) / "test_config.json"
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f)
    
    def tearDown(self):
        """Clean up after test."""
        self.temp_dir.cleanup()
    
    def test_init(self):
        """Test pipeline initialization."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'env_test_key', 'ELEVENLABS_API_KEY': 'env_test_key'}):
            pipeline = FactualPipeline(str(self.config_path))
            self.assertEqual(pipeline.config['openai_api_key'], 'test_openai_key')
            self.assertEqual(pipeline.config['elevenlabs_api_key'], 'test_elevenlabs_key')
    
    def test_init_with_env_vars(self):
        """Test pipeline initialization with environment variables."""
        config_no_keys = self.config.copy()
        config_no_keys['openai_api_key'] = ""
        config_no_keys['elevenlabs_api_key'] = ""
        
        config_path_no_keys = Path(self.temp_dir.name) / "test_config_no_keys.json"
        with open(config_path_no_keys, 'w') as f:
            json.dump(config_no_keys, f)
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'env_test_key', 'ELEVENLABS_API_KEY': 'env_test_key'}):
            pipeline = FactualPipeline(str(config_path_no_keys))
            self.assertEqual(pipeline.config['openai_api_key'], 'env_test_key')
            self.assertEqual(pipeline.config['elevenlabs_api_key'], 'env_test_key')
    
    @patch('subprocess.run')
    def test_extract_segment(self, mock_run):
        """Test extraction of video segment."""
        pipeline = FactualPipeline(str(self.config_path))
        
        input_path = "test_input.mp4"
        output_path = "test_output.mp4"
        start_time = 10.5
        duration = 5.0
        
        pipeline._extract_segment(input_path, output_path, start_time, duration)
        
        # Check that the correct command was executed
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "echo")  # Using echo instead of ffmpeg
        self.assertEqual(args[2], str(start_time))
        self.assertEqual(args[4], input_path)
        self.assertEqual(args[6], str(duration))
        self.assertEqual(args[9], output_path)
    
    @patch('subprocess.run')
    def test_add_watermark(self, mock_run):
        """Test adding watermark to video."""
        pipeline = FactualPipeline(str(self.config_path))
        
        input_path = "test_input.mp4"
        output_path = "test_output.mp4"
        
        pipeline._add_watermark(input_path, output_path)
        
        # Check that the correct command was executed
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "echo")  # Using echo instead of ffmpeg
        self.assertEqual(args[2], input_path)
        self.assertEqual(args[4], str(self.watermark_path))
        self.assertEqual(args[8], output_path)
    
    def test_intervention_dataclass(self):
        """Test the Intervention dataclass."""
        intervention = Intervention(
            timestamp_start=10.5,
            timestamp_end=15.0,
            claim_text="Test claim",
            intervention_text="Test intervention",
            intervention_type="correction",
            audio_file="test_audio.mp3",
            duration=4.5
        )
        
        self.assertEqual(intervention.timestamp_start, 10.5)
        self.assertEqual(intervention.timestamp_end, 15.0)
        self.assertEqual(intervention.claim_text, "Test claim")
        self.assertEqual(intervention.intervention_text, "Test intervention")
        self.assertEqual(intervention.intervention_type, "correction")
        self.assertEqual(intervention.audio_file, "test_audio.mp3")
        self.assertEqual(intervention.duration, 4.5)


if __name__ == "__main__":
    unittest.main() 