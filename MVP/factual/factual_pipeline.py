#!/usr/bin/env python3
"""
Factual - Instagram Reels Fact-Checking Pipeline

This script processes Instagram Reels, identifies factual claims,
provides corrective commentary, and outputs a composite video with
an optional summary frame showing truthfulness scores.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass, asdict, field
import argparse
import requests
from datetime import datetime
import re
import random
import platform

# Add PIL imports for proper text rendering
from PIL import Image, ImageDraw, ImageFont
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("factual")

class APIClientError(Exception):
    """Base exception for API client errors."""
    pass

class OpenAIClient:
    """Client for interacting with OpenAI APIs."""
    
    def __init__(self, api_key: str):
        """Initialize with OpenAI API key.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
        self._client = None
        
    @property
    def client(self):
        """Lazy-loaded OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise APIClientError("OpenAI package not installed. Install with: pip install openai")
        return self._client
        
    def transcribe_audio(self, audio_file_path: str, model: str = "large-v3") -> Dict[str, Any]:
        """Transcribe audio using OpenAI Whisper.
        
        Args:
            audio_file_path: Path to audio file
            model: Whisper model to use
            
        Returns:
            Transcription response
        """
        logger.info(f"Transcribing audio using OpenAI Whisper model: {model}")
        
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    response_format="verbose_json"
                )
            
            logger.info(f"Transcription completed successfully")
            return transcription.model_dump()
        except Exception as e:
            logger.error(f"OpenAI transcription failed: {str(e)}")
            raise APIClientError(f"Failed to transcribe audio: {str(e)}")
            
    def extract_claims(self, transcript_text: str) -> List[Dict[str, Any]]:
        """Extract factual claims and generate commentary using GPT-4o.
        
        Args:
            transcript_text: Full transcript text
            
        Returns:
            List of intervention objects with commentary
        """
        logger.info("Extracting factual claims using GPT-4o")
        
        system_prompt = """You are a fact-checking assistant that identifies factual claims in video transcripts 
and provides accurate and neutral commentary. For each factual claim you identify, determine if it is accurate or inaccurate
based on your knowledge (up to your training cutoff date).

For each claim:
1. Classify whether it's a factual claim or just an opinion/subjective statement
2. If it's a factual claim, assess its accuracy
3. Generate a brief, neutral correction for inaccurate claims or confirmation for accurate ones
4. Include credible sources when possible in your commentary

Format your response as a JSON object with an array field named "interventions".
Each intervention should have these fields:
- claim_text: The exact claim from the transcript
- intervention_text: Your factual commentary (correction or confirmation)
- intervention_type: Either "correction" or "confirmation"

Only identify meaningful factual claims that can be verified. Ignore opinions, subjective statements, or minor details.
Keep your commentary concise, neutral, and focused on factual accuracy."""

        user_prompt = f"""Here is the transcript from an Instagram Reel that I need you to fact-check. 
Identify all factual claims and provide appropriate commentary.

TRANSCRIPT:
{transcript_text}

Please format your response as a JSON object with an array field named "interventions".
Each intervention should contain:
- claim_text: The exact claim from the transcript
- intervention_text: Your factual commentary (correction or confirmation)
- intervention_type: Either "correction" or "confirmation"

Example format:
{{
  "interventions": [
    {{
      "claim_text": "The Earth is flat",
      "intervention_text": "The Earth is an oblate spheroid, not flat",
      "intervention_type": "correction"
    }},
    ...
  ]
}}

Only include meaningful factual statements that require verification."""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Parse the response
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Extract interventions from various possible response formats
            interventions_data = []
            if "interventions" in result:
                interventions_data = result["interventions"]
            elif "claim_text" in result and "intervention_text" in result and "intervention_type" in result:
                # Single intervention object
                interventions_data = [result]
            elif isinstance(result, list):
                interventions_data = result
            else:
                # Look for any key that could contain an array of interventions
                for key, value in result.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict) and "claim_text" in value[0]:
                            interventions_data = value
                            break
            
            logger.info(f"Extracted {len(interventions_data)} factual claims")
            return interventions_data
            
        except Exception as e:
            logger.error(f"GPT-4o claim extraction failed: {str(e)}")
            raise APIClientError(f"Failed to extract claims: {str(e)}")

class ElevenLabsClient:
    """Client for interacting with ElevenLabs API."""
    
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        """Initialize with ElevenLabs API key.
        
        Args:
            api_key: ElevenLabs API key
            voice_id: Default voice ID to use
        """
        self.api_key = api_key
        self.voice_id = voice_id
        self.base_url = "https://api.elevenlabs.io/v1"
        
    def validate_api_key(self) -> bool:
        """Validate the API key by making a test request.
        
        Returns:
            True if valid, raises exception if invalid
        """
        logger.info("Validating ElevenLabs API key")
        
        try:
            response = requests.get(
                f"{self.base_url}/user",
                headers={"xi-api-key": self.api_key}
            )
            
            if response.status_code == 401:
                raise APIClientError(
                    "ElevenLabs API key is invalid or expired. Please check your API key at "
                    "https://elevenlabs.io/app/account and update it in your config."
                )
            elif response.status_code == 403:
                raise APIClientError(
                    "ElevenLabs API key lacks permission. Your subscription may have expired or "
                    "you're using a key with insufficient privileges."
                )
            elif response.status_code >= 400:
                raise APIClientError(
                    f"ElevenLabs API error (HTTP {response.status_code}): {response.text}. "
                    "Check your API key and account status."
                )
                
            response.raise_for_status()
            
            # Verify subscription status
            user_data = response.json()
            subscription = user_data.get("subscription", {})
            status = subscription.get("status")
            tier = subscription.get("tier")
            
            if status == "expired":
                raise APIClientError(
                    "Your ElevenLabs subscription has expired. Please renew your subscription at "
                    "https://elevenlabs.io/app/subscription"
                )
            
            character_count = subscription.get("character_count", 0)
            character_limit = subscription.get("character_limit", 0)
            
            if character_limit > 0 and character_count >= character_limit:
                logger.warning(
                    f"Your ElevenLabs character limit has been reached ({character_count}/{character_limit}). "
                    "TTS generation may fail. Consider upgrading your plan."
                )
            
            logger.info(f"ElevenLabs API key is valid (Plan: {tier})")
            return True
            
        except requests.RequestException as e:
            # Only treat authentication failure as fatal
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                raise APIClientError(f"ElevenLabs API key validation failed: {str(e)}")
            
            logger.warning(f"ElevenLabs API key validation warning: {str(e)}")
            return False
    
    def generate_speech(self, text: str, output_path: str, 
                       voice_id: Optional[str] = None,
                       speed: float = 1.0) -> Dict[str, Any]:
        """Generate speech using the ElevenLabs API.
        
        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            voice_id: Voice ID to use (defaults to instance default)
            speed: Speed factor (1.0 is normal speed)
            
        Returns:
            Dictionary with metadata including duration
        """
        if not voice_id:
            voice_id = self.voice_id
            
        logger.info(f"Generating speech with ElevenLabs (speed: {speed:.2f})")
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        # Default voice settings
        voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True,
            "speed": speed
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": voice_settings
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
                
            # Get audio duration using FFmpeg
            ffmpeg_path = "ffmpeg"  # This should be provided by the caller ideally
            result = subprocess.run(
                [ffmpeg_path, "-i", output_path, "-f", "null", "-"],
                stderr=subprocess.PIPE, text=True, check=True
            )
            
            duration_str = [line for line in result.stderr.split('\n') if "Duration" in line][0]
            duration_parts = duration_str.split("Duration: ")[1].split(",")[0].split(":")
            duration = float(duration_parts[0]) * 3600 + float(duration_parts[1]) * 60 + float(duration_parts[2])
            
            logger.info(f"Generated speech ({duration:.2f}s) saved to {output_path}")
            
            return {
                "path": output_path,
                "duration": duration,
                "speed": speed
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ElevenLabs API request failed: {str(e)}")
            raise APIClientError(f"Failed to generate speech: {str(e)}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed to get audio duration: {e.stderr}")
            # Still return data without duration
            return {
                "path": output_path,
                "duration": None,
                "speed": speed
            }
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}")
            raise APIClientError(f"Failed to generate speech: {str(e)}")

class FFmpegHelper:
    """Helper class to centralize FFmpeg operations."""
    
    def __init__(self, ffmpeg_path: str):
        """Initialize with path to FFmpeg binary.
        
        Args:
            ffmpeg_path: Path to the FFmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path
    
    def calculate_text_box_params(self, width: int, height: int) -> Dict[str, Any]:
        """Calculate standardized text box parameters that guarantee 80% width positioning.
        
        This ensures ALL text overlays use consistent sizing and positioning:
        - Text box width: exactly 80% of frame width
        - Text box position: starts at 10% from left edge, ends at 90%
        - Text is centered within this 80% area
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            
        Returns:
            Dict with keys: text_width_px, text_x_offset_px, text_area_start_pct, text_area_end_pct
        """
        # Fixed constraints - these define the 80% rule
        TEXT_AREA_START_PCT = 0.10  # 10% from left edge
        TEXT_AREA_END_PCT = 0.90    # 90% from left edge  
        TEXT_WIDTH_PCT = TEXT_AREA_END_PCT - TEXT_AREA_START_PCT  # = 0.80 (80%)
        
        # Calculate pixel values
        text_width_px = int(width * TEXT_WIDTH_PCT)
        text_x_offset_px = int(width * TEXT_AREA_START_PCT)
        
        return {
            'text_width_px': text_width_px,
            'text_x_offset_px': text_x_offset_px,
            'text_area_start_pct': TEXT_AREA_START_PCT,
            'text_area_end_pct': TEXT_AREA_END_PCT,
            'text_width_pct': TEXT_WIDTH_PCT
        }
        
    def run_command(self, args: List[str], check: bool = True, 
                   capture_output: bool = True, text: bool = False) -> subprocess.CompletedProcess:
        """Run an FFmpeg command with specified arguments.
        
        Args:
            args: List of command arguments (without ffmpeg path)
            check: Whether to check return code
            capture_output: Whether to capture stdout/stderr
            text: Whether to decode stdout/stderr as text
            
        Returns:
            CompletedProcess instance
        """
        cmd = [self.ffmpeg_path] + args
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=text)
    
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get information about a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video information (width, height, duration)
        """
        args = [
            "-i", video_path,
            "-f", "null", "-"
        ]
        
        result = self.run_command(args, check=False, capture_output=True, text=True)
        
        # Extract width and height
        width_height = [line for line in result.stderr.split('\n') 
                        if " [Parsed_crop" not in line and (", DAR" in line or "Video: " in line)]
                        
        width, height = 1080, 1920  # Default to portrait mode
        
        if width_height:
            parts = width_height[0].split()
            resolution_parts = None
            
            # Look for resolution pattern like 1080x1920
            for part in parts:
                if 'x' in part and part[0].isdigit() and part[-1].isdigit():
                    try:
                        width, height = map(int, part.split('x'))
                        resolution_parts = [width, height]
                        break
                    except (ValueError, IndexError):
                        continue
            
            if resolution_parts:
                width, height = resolution_parts
        
        # Extract duration
        duration = 30.0  # Default
        try:
            duration_line = [line for line in result.stderr.split('\n') if "Duration: " in line][0]
            duration_parts = duration_line.split("Duration: ")[1].split(",")[0].split(":")
            duration = float(duration_parts[0]) * 3600 + float(duration_parts[1]) * 60 + float(duration_parts[2])
        except (IndexError, ValueError):
            logger.warning("Could not parse video duration, using default of 30 seconds")
        
        return {
            "width": width,
            "height": height,
            "duration": duration
        }
    
    def has_audio(self, file_path: str) -> bool:
        """Check if a file has an audio track.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Boolean indicating if the file has audio
        """
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False
            
        args = [
            "-i", file_path,
            "-hide_banner"
        ]
        
        result = self.run_command(args, check=False, capture_output=True, text=True)
        return "Audio: " in result.stderr
    
    def extract_segment(self, input_path: str, output_path: str, 
                       start_time: float, duration: float) -> bool:
        """Extract a segment from a video.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the output segment
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            Boolean indicating success
        """
        # Ensure valid start time and duration
        start_time = max(0.0, start_time)
        if duration <= 0:
            logger.error(f"Invalid duration: {duration}")
            return False
        
        # Try different methods in order of preference
        methods = ["efficient" if duration > 5.0 else "two_pass", "accurate", "segment_muxer"] 
        
        for method in methods:
            if self._extract_segment_with_method(input_path, output_path, start_time, duration, method):
                return True
                
        logger.error(f"All extraction methods failed for segment at {start_time:.2f}s")
        return False
    
    def _extract_segment_with_method(self, input_path: str, output_path: str,
                                    start_time: float, duration: float, 
                                    method: str) -> bool:
        """Extract a segment using a specific method.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the output segment
            start_time: Start time in seconds
            duration: Duration in seconds
            method: Extraction method name
            
        Returns:
            Boolean indicating success
        """
        logger.info(f"Extracting {duration:.2f}s segment from {start_time:.2f}s using {method} method")
        
        if method == "two_pass":
            # First pass: Extract raw segment
            temp_output = f"{output_path}.temp.mp4"
            args = [
                "-ss", str(start_time),
                "-i", input_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                temp_output
            ]
            
            try:
                self.run_command(args, check=True, capture_output=True)
                
                # Second pass: Re-encode with careful settings for audio
                if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                    final_args = [
                        "-i", temp_output,
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-af", "volume=1.0",
                        "-y",
                        output_path
                    ]
                    
                    self.run_command(final_args, check=True, capture_output=True)
                    
                    # Verify the output has audio
                    if self.has_audio(output_path):
                        logger.info(f"Two-pass extraction worked!")
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                        return True
            except Exception as e:
                logger.warning(f"Two-pass method failed: {str(e)}")
                
            # Clean up temp file if it exists
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except Exception:
                    pass
                    
        elif method == "accurate":
            # Single-pass with accurate seeking (after input for accuracy)
            args = [
                "-i", input_path,
                "-ss", str(start_time),
                "-t", str(duration),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                output_path
            ]
            
            try:
                self.run_command(args, check=True, capture_output=True)
                
                # Verify the output has audio
                if self.has_audio(output_path):
                    logger.info(f"Accurate seeking method worked!")
                    return True
            except Exception as e:
                logger.warning(f"Accurate seeking method failed: {str(e)}")
                
        elif method == "segment_muxer":
            # Use FFmpeg's segment muxer (very reliable but may have slight timing issues)
            args = [
                "-i", input_path,
                "-f", "segment",
                "-segment_start_time", str(start_time),
                "-segment_time", str(duration),
                "-segment_times", str(start_time),
                "-segment_list", f"{output_path}.list.txt",
                "-reset_timestamps", "1",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0",
                "-y",
                f"{output_path}.seg%03d.mp4"
            ]
            
            try:
                self.run_command(args, check=True, capture_output=True)
                
                # Find the segment file
                import glob
                segment_files = glob.glob(f"{output_path}.seg*.mp4")
                
                if segment_files and os.path.exists(segment_files[0]) and os.path.getsize(segment_files[0]) > 0:
                    # Rename the first segment to the desired output
                    import shutil
                    shutil.copy2(segment_files[0], output_path)
                    
                    # Verify the output has audio
                    if self.has_audio(output_path):
                        logger.info(f"Segment muxer method worked!")
                        
                        # Clean up segment files
                        for f in segment_files:
                            try:
                                os.remove(f)
                            except Exception:
                                pass
                        if os.path.exists(f"{output_path}.list.txt"):
                            try:
                                os.remove(f"{output_path}.list.txt")
                            except Exception:
                                pass
                                
                        return True
            except Exception as e:
                logger.warning(f"Segment muxer method failed: {str(e)}")
        
        elif method == "efficient":
            # Efficient method for long segments
            args = [
                "-ss", str(start_time),
                "-i", input_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                output_path
            ]
            
            try:
                self.run_command(args, check=True, capture_output=True)
                
                # Verify the output has audio
                if self.has_audio(output_path):
                    logger.info(f"Efficient method worked!")
                    return True
            except Exception as e:
                logger.warning(f"Efficient extraction failed: {str(e)}")
        
        return False
    
    def create_black_frame_with_text(self, output_path: str, text: str, 
                                    width: int, height: int, duration: float, 
                                    audio_path: Optional[str] = None,
                                    watermark_path: Optional[str] = None) -> bool:
        """Create a black frame with text overlay and optional audio.
        
        Args:
            output_path: Path to save the output video
            text: Text to overlay on the black frame
            width: Width of the output video
            height: Height of the output video
            duration: Duration in seconds
            audio_path: Optional path to audio file to include
            watermark_path: Optional path to watermark image
            
        Returns:
            Boolean indicating success
        """
        # Format text for FFmpeg
        formatted_text, temp_text_file_path = self._format_text_for_overlay(text, width)
        
        try:
            # Build filter complex parts
            filter_parts = []
            inputs = ["-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}"]
            
            # Add text overlay with centralized positioning calculation
            fontsize = 42
            text_y_position = height * 0.8  # Start at 80% from top
            
            # Use centralized text box calculation for consistent 80% width positioning
            ffmpeg_helper = FFmpegHelper(self.config['ffmpeg_path'])
            text_params = ffmpeg_helper.calculate_text_box_params(width, height)
            x_offset_px = text_params['text_x_offset_px']  # Exact 10% offset
            target_w_px = text_params['text_width_px']     # Exact 80% width
            
            if not formatted_text.strip():
                text_filter = f"drawtext=text=' ':fontcolor=white:fontsize={fontsize}:x={x_offset_px}:y={text_y_position}:boxw={target_w_px}:line_spacing=20:borderw=2:bordercolor=black@0.5:box=1:boxcolor=black@0.5:boxborderw=10:expansion=none"
            else:
                safe_text_file_path = temp_text_file_path.replace("\\", "/") if temp_text_file_path else ""
                text_filter = f"drawtext=textfile='{safe_text_file_path}':fontcolor=white:fontsize={fontsize}:x={x_offset_px}:y={text_y_position}:boxw={target_w_px}:line_spacing=20:borderw=2:bordercolor=black@0.5:box=1:boxcolor=black@0.5:boxborderw=10:expansion=none"
            
            filter_parts.append(f"[0:v]{text_filter}[v_text]")
            current_v_label = "[v_text]"
            
            # Add watermark if provided
            if watermark_path and os.path.exists(watermark_path):
                inputs.extend(["-i", watermark_path])
                
                target_wm_height = int(height * 0.1)  # 10% of screen height for watermark (2x smaller)
                target_wm_height = max(20, target_wm_height)
                
                filter_parts.append(
                    f"[1:v]format=rgba,colorchannelmixer=aa=1.0,scale=w=-2:h={target_wm_height}[wm_scaled];"
                    f"{current_v_label}[wm_scaled]overlay=x=(W-w)/2:y=H-h-H*0.01[v_with_wm]"
                )
                current_v_label = "[v_with_wm]"
            
            # Add audio if provided
            audio_valid = audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
            
            # Build final command
            cmd = inputs.copy()
            
            if audio_valid:
                cmd.extend(["-i", audio_path])
                cmd.extend([
                    "-filter_complex", ";".join(filter_parts),
                    "-map", current_v_label, 
                    "-map", "2:a",
                    "-c:v", "libx264",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-y", output_path
                ])
            else:
                cmd.extend([
                    "-filter_complex", ";".join(filter_parts),
                    "-map", current_v_label,
                    "-c:v", "libx264",
                    "-an", "-t", str(duration),
                    "-y", output_path
                ])
            
            # Run command
            self.run_command(cmd, check=True, capture_output=True)
            
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            
        except Exception as e:
            logger.error(f"Error creating black frame: {str(e)}")
            
            # Try simplified fallback
            try:
                fallback_cmd = [
                    "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}",
                ]
                
                fallback_text_y = height * 0.8  # Position at 80% height for fallback too
                # Use centralized calculation for consistent positioning even in fallback
                ffmpeg_helper = FFmpegHelper(self.config['ffmpeg_path'])
                text_params = ffmpeg_helper.calculate_text_box_params(width, height)
                x_offset_px = text_params['text_x_offset_px']
                target_w_px = text_params['text_width_px']
                
                if audio_valid:
                    fallback_cmd.extend(["-i", audio_path])
                    fallback_cmd.extend([
                        "-vf", f"drawtext=text=' ':fontcolor=white:fontsize=42:x={x_offset_px}:y={fallback_text_y}:boxw={target_w_px}:expansion=none",
                        "-c:v", "libx264", 
                        "-c:a", "aac", 
                        "-shortest", 
                        "-y", output_path
                    ])
                else:
                    fallback_cmd.extend([
                        "-vf", f"drawtext=text=' ':fontcolor=white:fontsize=42:x={x_offset_px}:y={fallback_text_y}:boxw={target_w_px}:expansion=none",
                        "-c:v", "libx264",
                        "-an",
                        "-t", str(duration),
                        "-y", output_path
                    ])
                
                self.run_command(fallback_cmd, check=True, capture_output=True)
                logger.info(f"Created black frame with simplified method: {output_path}")
                return True
            except Exception as e2:
                logger.error(f"Fallback method also failed: {str(e2)}")
                return False
        finally:
            # Clean up temporary text file
            if temp_text_file_path and os.path.exists(temp_text_file_path):
                try:
                    os.remove(temp_text_file_path)
                except Exception:
                    pass
    
    def _format_text_for_overlay(self, text: str, width: int) -> Tuple[str, Optional[str]]:
        """Format text for FFmpeg overlay with proper line wrapping.
        
        Args:
            text: Text to format
            width: Video width for calculating line length
            
        Returns:
            Tuple of (formatted_text, temp_file_path) where temp_file_path may be None
        """
        words = text.split()
        lines = []
        current_line = ""
        
        fontsize = 42
        
        # Use centralized text box calculation for consistent 80% width
        ffmpeg_helper = FFmpegHelper(self.config['ffmpeg_path'])
        text_params = ffmpeg_helper.calculate_text_box_params(width, 1920)  # Height not needed for width calc
        target_text_width = text_params['text_width_px']
        avg_char_width_factor = 0.55  # Heuristic for average character width relative to fontsize
        avg_char_width_approx = fontsize * avg_char_width_factor
        
        max_chars_per_line = int(target_text_width / avg_char_width_approx) if avg_char_width_approx > 0 else 30
        max_chars_per_line = max(10, max_chars_per_line)

        # Line-wrapping logic
        for word in words:
            if not current_line:  # If current_line is empty
                current_line = word
            elif len(current_line) + 1 + len(word) <= max_chars_per_line:  # If word fits with a space
                current_line += " " + word
            else:  # Word does not fit
                lines.append(current_line)
                current_line = word
        
        if current_line:  # Append the last line
            lines.append(current_line)
        
        formatted_text = "\n".join(lines)
        
        # Create text file for FFmpeg if needed
        temp_file_path = None
        if formatted_text.strip():
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt", encoding='utf-8') as tmp_f:
                tmp_f.write(formatted_text)
                temp_file_path = tmp_f.name
        
        return formatted_text, temp_file_path
    
    def add_watermark(self, input_path: str, output_path: str, watermark_path: str) -> bool:
        """Add a watermark to a video.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the output video
            watermark_path: Path to the watermark image
            
        Returns:
            Boolean indicating success
        """
        if not os.path.exists(watermark_path):
            logger.error(f"Watermark file not found: {watermark_path}")
            return False
            
        # Check if input has audio
        has_audio = self.has_audio(input_path)
        
        try:
            # Scale watermark to 15% of video height (1.5x bigger than previous 10%), and overlay
            filter_complex = (
                "[1:v]scale=w=-2:h=ih*0.1875[scaled_wm];"
                "[scaled_wm]format=rgba,colorchannelmixer=aa=1[final_wm];"
                "[0:v][final_wm]overlay=x=(W-w)/2:y=H*0.10"
            )
            
            args = [
                "-i", input_path,
                "-i", watermark_path,
                "-filter_complex", filter_complex,
                "-c:v", "libx264",
            ]
            
            if has_audio:
                args.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                args.extend(["-an"])
            
            args.extend(["-y", output_path])
            
            self.run_command(args, check=True, capture_output=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully added watermark")
                return True
                
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            
            # Try simplified watermark method
            try:
                fallback_args = [
                    "-i", input_path,
                    "-i", watermark_path,
                    "-filter_complex", "[0:v][1:v]overlay=10:10",
                    "-c:a", "copy",
                    "-y", output_path
                ]
                
                self.run_command(fallback_args, check=True, capture_output=True)
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Added watermark with fallback method")
                    return True
            except Exception as e2:
                logger.error(f"Fallback watermark method failed: {str(e2)}")
        
        return False
    
    def concatenate_videos(self, segment_files: List[str], output_path: str) -> bool:
        """Concatenate multiple video files.
        
        Args:
            segment_files: List of paths to video segments
            output_path: Path to save the concatenated video
            
        Returns:
            Boolean indicating success
        """
        if not segment_files:
            logger.error("No segments to concatenate")
            return False
            
        # Try different methods in order of preference
        methods = ["filter_complex", "concat_demuxer", "segment_by_segment"]
        
        for method in methods:
            if self._concatenate_with_method(segment_files, output_path, method):
                return True
                
        logger.error("All concatenation methods failed")
        return False
    
    def _concatenate_with_method(self, segment_files: List[str], output_path: str, method: str) -> bool:
        """Concatenate videos using a specific method.
        
        Args:
            segment_files: List of paths to video segments
            output_path: Path to save the concatenated video
            method: Concatenation method name
            
        Returns:
            Boolean indicating success
        """
        logger.info(f"Concatenating {len(segment_files)} segments using {method} method")
        
        if method == "filter_complex":
            try:
                # Build input arguments for each segment
                input_args = []
                for segment in segment_files:
                    input_args.extend(["-i", segment])
                
                # Create filter complex
                inputs_count = len(segment_files)
                video_inputs = []
                audio_inputs = []
                
                for i in range(inputs_count):
                    video_inputs.append(f"[{i}:v]")
                    audio_inputs.append(f"[{i}:a]")
                
                video_concat = f"{' '.join(video_inputs)}concat=n={inputs_count}:v=1:a=0[vout]"
                audio_concat = f"{' '.join(audio_inputs)}concat=n={inputs_count}:v=0:a=1[aout]"
                
                filter_complex = f"{video_concat};{audio_concat}"
                
                args = [
                    *input_args,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ac", "2",
                    "-ar", "48000",
                    "-y",
                    output_path
                ]
                
                self.run_command(args, check=True, capture_output=True)
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0 and self.has_audio(output_path):
                    logger.info("Concatenated videos with filter_complex method")
                    return True
            except Exception as e:
                logger.warning(f"filter_complex concat failed: {str(e)}")
                
        elif method == "concat_demuxer":
            try:
                # Create concat file
                concat_file = f"{output_path}.concat.txt"
                with open(concat_file, 'w') as f:
                    for segment in segment_files:
                        f.write(f"file '{os.path.abspath(segment)}'\n")
                
                args = [
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file,
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ac", "2",
                    "-ar", "48000",
                    "-y",
                    output_path
                ]
                
                self.run_command(args, check=True, capture_output=True)
                
                # Clean up concat file
                if os.path.exists(concat_file):
                    try:
                        os.remove(concat_file)
                    except Exception:
                        pass
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0 and self.has_audio(output_path):
                    logger.info("Concatenated videos with concat demuxer method")
                    return True
            except Exception as e:
                logger.warning(f"concat_demuxer failed: {str(e)}")
                
        elif method == "segment_by_segment":
            try:
                # Start with first segment
                import shutil
                first_segment = segment_files[0]
                shutil.copy2(first_segment, output_path)
                
                temp_path = output_path
                
                # Append each additional segment
                for i in range(1, len(segment_files)):
                    segment_path = segment_files[i]
                    next_temp = f"{output_path}.concat_{i}.mp4"
                    
                    args = [
                        "-i", temp_path,
                        "-i", segment_path,
                        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vout];[0:a][1:a]concat=n=2:v=0:a=1[aout]",
                        "-map", "[vout]", 
                        "-map", "[aout]",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-y",
                        next_temp
                    ]
                    
                    self.run_command(args, check=True, capture_output=True)
                    
                    if os.path.exists(next_temp) and os.path.getsize(next_temp) > 0:
                        if i > 1 and os.path.exists(temp_path) and temp_path != output_path:
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                        
                        temp_path = next_temp
                    else:
                        break
                
                # If we have a final result, copy it to output
                if temp_path != output_path and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    shutil.copy2(temp_path, output_path)
                    
                    # Clean up temporary files
                    for i in range(1, len(segment_files)):
                        temp_file = f"{output_path}.concat_{i}.mp4"
                        if os.path.exists(temp_file):
                            try:
                                os.remove(temp_file)
                            except Exception:
                                pass
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0 and self.has_audio(output_path):
                    logger.info("Concatenated videos with segment-by-segment method")
                    return True
            except Exception as e:
                logger.warning(f"segment_by_segment failed: {str(e)}")
        
        return False
    
    def normalize_audio(self, input_path: str, output_path: str) -> bool:
        """Normalize audio in a video file.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the normalized video
            
        Returns:
            Boolean indicating success
        """
        try:
            args = [
                "-i", input_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-ar", "48000",
                "-ac", "2",
                "-b:a", "192k",
                "-af", "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-y",
                output_path
            ]
            
            self.run_command(args, check=True, capture_output=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0 and self.has_audio(output_path):
                return True
        except Exception as e:
            logger.warning(f"Audio normalization failed: {str(e)}")
            
        return False

class ErrorHandler:
    """Centralized error handling with retry logic."""
    
    def __init__(self, max_retries: int = 3, retry_delay: int = 2, 
                logger: Optional[logging.Logger] = None):
        """Initialize error handler.
        
        Args:
            max_retries: Maximum number of retries
            retry_delay: Initial delay between retries (doubled after each attempt)
            logger: Logger instance to use
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or logging.getLogger("factual")
    
    def execute_with_retry(self, func: callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function
            
        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}. "
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"All {self.max_retries} attempts failed.")
        
        # If we get here, all retries failed
        raise last_exception
    
    def safe_cleanup(self, file_path: str) -> bool:
        """Safely remove a file if it exists.
        
        Args:
            file_path: Path to the file to remove
            
        Returns:
            True if successful or file didn't exist, False if removal failed
        """
        if not file_path or not os.path.exists(file_path):
            return True
            
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            self.logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")
            return False

class SegmentProcessor:
    """Processor for handling video segments and their operations."""
    
    def __init__(self, ffmpeg: FFmpegHelper, error_handler: ErrorHandler, 
                temp_dir: str, debug_options: Dict[str, bool] = None):
        """Initialize the segment processor.
        
        Args:
            ffmpeg: FFmpeg helper instance
            error_handler: Error handler instance
            temp_dir: Directory for temporary files
            debug_options: Dictionary of debug options
        """
        self.ffmpeg = ffmpeg
        self.error_handler = error_handler
        self.temp_dir = temp_dir
        self.debug_options = debug_options or {}
        self.logger = error_handler.logger
    
    def extract_segment(self, source_video: str, start_time: float, duration: float) -> Optional[str]:
        """Extract a segment from the source video.
        
        Args:
            source_video: Path to the source video
            start_time: Start time in seconds
            duration: Duration in seconds
            
        Returns:
            Path to the extracted segment, or None if extraction failed
        """
        if duration <= 0.01:  # Skip very short segments
            self.logger.info(f"Skipping segment extraction as duration is too short ({duration:.2f}s)")
            return None
            
        # Create unique output path
        segment_id = str(uuid.uuid4())[:8]
        segment_dir = os.path.join(self.temp_dir, "segments")
        os.makedirs(segment_dir, exist_ok=True)
        output_path = os.path.join(segment_dir, f"segment_{segment_id}.mp4")
        
        # Try to extract the segment
        try:
            self.logger.info(f"Extracting segment from {start_time:.2f}s for {duration:.2f}s")
            if self.ffmpeg.extract_segment(source_video, output_path, start_time, duration):
                # Debug: Save segment for individual inspection if needed
                if self.debug_options.get('debug_save_segments', False):
                    debug_dir = os.path.join(os.path.dirname(self.temp_dir), "debug_segments")
                    os.makedirs(debug_dir, exist_ok=True)
                    debug_path = os.path.join(debug_dir, f"original_{segment_id}.mp4")
                    import shutil
                    shutil.copy2(output_path, debug_path)
                    self.logger.info(f"Saved debug segment to {debug_path}")
                
                return output_path
            else:
                self.logger.error(f"Failed to extract segment from {start_time:.2f}s")
                return None
        except Exception as e:
            self.logger.error(f"Error extracting segment: {str(e)}")
            return None
    
    def create_intervention_segment(self, text: str, audio_path: str, width: int, height: int, 
                                 intervention_type: str = None, watermark_path: str = None) -> Optional[str]:
        """Create a segment for an intervention with black background and text.
        
        Args:
            text: Text to display
            audio_path: Path to the audio file
            width: Width of the video
            height: Height of the video
            intervention_type: Type of intervention (correction or confirmation)
            watermark_path: Path to watermark image
            
        Returns:
            Path to the created segment, or None if creation failed
        """
        # Set appropriate watermark based on intervention type if not provided
        if not watermark_path and intervention_type:
            if intervention_type == "correction" and 'bs_watermark_path' in self.debug_options:
                watermark_path = self.debug_options.get('bs_watermark_path')
            elif intervention_type == "confirmation" and 'verified_watermark_path' in self.debug_options:
                watermark_path = self.debug_options.get('verified_watermark_path')
        
        # Get audio duration
        duration = 5.0  # Default duration
        if audio_path and os.path.exists(audio_path):
            try:
                audio_info_cmd = [
                    self.ffmpeg.ffmpeg_path, "-i", audio_path, "-f", "null", "-"
                ]
                audio_info = subprocess.run(
                    audio_info_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
                )
                
                for line in audio_info.stderr.split('\n'):
                    if "Duration" in line:
                        time_parts = line.split("Duration: ")[1].split(",")[0].split(":")
                        duration = float(time_parts[0]) * 3600 + float(time_parts[1]) * 60 + float(time_parts[2])
                        break
            except Exception as e:
                self.logger.warning(f"Could not determine audio duration: {str(e)}")
        
        # Create segment
        segment_id = str(uuid.uuid4())[:8]
        segment_dir = os.path.join(self.temp_dir, "segments")
        os.makedirs(segment_dir, exist_ok=True)
        output_path = os.path.join(segment_dir, f"intervention_{segment_id}.mp4")
        
        try:
            self.logger.info(f"Creating intervention segment with text: '{text[:50]}...'")
            if self.ffmpeg.create_black_frame_with_text(
                output_path, text, width, height, duration, audio_path, watermark_path
            ):
                # Debug: Save segment for individual inspection if needed
                if self.debug_options.get('debug_save_segments', False):
                    debug_dir = os.path.join(os.path.dirname(self.temp_dir), "debug_segments")
                    os.makedirs(debug_dir, exist_ok=True)
                    debug_path = os.path.join(debug_dir, f"intervention_{segment_id}.mp4")
                    import shutil
                    shutil.copy2(output_path, debug_path)
                    self.logger.info(f"Saved debug intervention segment to {debug_path}")
                
                return output_path
            else:
                self.logger.error(f"Failed to create intervention segment")
                return None
        except Exception as e:
            self.logger.error(f"Error creating intervention segment: {str(e)}")
            return None
    
    def normalize_segments(self, segment_paths: List[str]) -> List[str]:
        """Normalize audio levels across segments for consistent output.
        
        Args:
            segment_paths: List of paths to segments
            
        Returns:
            List of paths to normalized segments
        """
        normalized_paths = []
        
        for i, segment_path in enumerate(segment_paths):
            if not os.path.exists(segment_path):
                self.logger.warning(f"Segment {i} does not exist, skipping normalization")
                normalized_paths.append(segment_path)  # Keep original path in list
                continue
                
            norm_path = f"{segment_path}.norm.mp4"
            
            try:
                self.logger.info(f"Normalizing audio for segment {i}")
                if self.ffmpeg.normalize_audio(segment_path, norm_path):
                    normalized_paths.append(norm_path)
                else:
                    self.logger.warning(f"Failed to normalize segment {i}, using original")
                    normalized_paths.append(segment_path)
            except Exception as e:
                self.logger.warning(f"Error normalizing segment {i}: {str(e)}, using original")
                normalized_paths.append(segment_path)
        
        return normalized_paths
    
    def create_composite_video(self, segments: List[str], output_path: str) -> bool:
        """Create a composite video from multiple segments.
        
        Args:
            segments: List of paths to segments
            output_path: Path to save the output video
            
        Returns:
            Success status
        """
        if not segments:
            self.logger.error("No segments provided for composite video")
            return False
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # First, normalize all segments
        self.logger.info(f"Normalizing {len(segments)} segments")
        normalized_segments = self.normalize_segments(segments)
        
        # Then concatenate them
        self.logger.info(f"Concatenating {len(normalized_segments)} segments")
        if self.ffmpeg.concatenate_videos(normalized_segments, output_path):
            self.logger.info(f"Created composite video at {output_path}")
            
            # Clean up normalized segments (not original ones)
            for i, path in enumerate(normalized_segments):
                if path != segments[i]:  # Only remove normalized versions
                    self.error_handler.safe_cleanup(path)
            
            return True
        else:
            self.logger.error(f"Failed to concatenate segments")
            return False

# Constants
DEFAULT_CONFIG = {
    "openai_api_key": "",
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",  # Default voice
                "whisper_model": "whisper-1",
    "watermark_path": "assets/logo_watermark.png",
    "output_dir": "output",
    "temp_dir": "temp",
    "ffmpeg_path": "ffmpeg",
    "yt_dlp_path": "yt-dlp",
    "max_retries": 3,
    "retry_delay": 2,
    # Intervention watermarks
    "verified_watermark_path": "assets/verified_watermark.png",
    "bs_watermark_path": "assets/bs_watermark.png",
    # Intervention limits and timing
    "max_interventions": 4,              # Maximum number of interventions to include
    "min_segment_duration": 3.0,         # Minimum duration in seconds for original segments
    "min_opening_original_duration": 1.0,  # Guarantee at least this many seconds of original footage at the very start
    "merge_short_segments": True,        # Merge interventions if original segment is too short
    "max_intervention_text_length": 350, # Maximum characters for intervention text (increased for readability)
    "use_ai_text_condensation": True,    # Use OpenAI to intelligently condense long intervention text while preserving meaning
    "enable_tts_speed_adjustment": True, # Enable TTS speed adjustment to match target durations (experimental, may cause API errors)
    "use_natural_intervention_timing": False, # Use actual TTS duration instead of forcing original segment timing
    "render_intervention_text": True,       # Whether to render text overlays on interventions (false = watermarks only)
    "include_summary_frame": True,          # Whether to include a summary frame at the end showing claims and truthfulness score
    "summary_frame_duration": 8.0,         # Duration of the summary frame in seconds
    "max_summary_claims": 5,               # Maximum number of claims to show in summary
    # Summary slide generation
    "generate_summary_slide": True,        # Generate a separate PNG summary slide for manual addition
    "summary_slide_width": 1080,           # Width of the summary slide (Instagram standard)
    "summary_slide_height": 1920,          # Height of the summary slide (Instagram story format)
    # Sentence-aware cutting
    "enable_sentence_aware_cuts": True,
    "sentence_cut_max_lookbehind": 3.0,  # Seconds
    "sentence_cut_max_lookahead": 2.0,   # Seconds
    # Debugging options
    "debug_visual_checkpoints": False,   # Enable visual frame extraction at key points
    "debug_save_segments": False,        # Save each segment as a separate file
    "debug_sequence_manifest": False,    # Generate detailed JSON sequence manifest
    "use_sample_video": False,           # Use a sample video instead of downloading from Instagram
}

@dataclass
class Intervention:
    """Represents a fact-checking intervention in the video."""
    timestamp_start: float
    timestamp_end: float
    claim_text: str
    intervention_text: str
    intervention_type: str  # 'correction' or 'confirmation'
    target_duration: Optional[float] = None # Add this line
    audio_file: Optional[str] = None
    duration: Optional[float] = None
    # New: list of source dictionaries, each with description and url
    sources: Optional[List[Dict[str, str]]] = field(default_factory=list)


class FactualPipeline:
    """Main pipeline for fact-checking Instagram Reels."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the pipeline with configuration.
        
        Args:
            config_path: Path to the configuration JSON file
        """
        self.config = DEFAULT_CONFIG.copy()
        if config_path:
            self._load_config(config_path)
        
        # Set API keys from environment if available
        if not self.config['openai_api_key']:
            self.config['openai_api_key'] = os.environ.get('OPENAI_API_KEY', '')
        if not self.config['elevenlabs_api_key']:
            self.config['elevenlabs_api_key'] = os.environ.get('ELEVENLABS_API_KEY', '')
        
        # Create necessary directories
        os.makedirs(self.config['output_dir'], exist_ok=True)
        os.makedirs(self.config['temp_dir'], exist_ok=True)
        os.makedirs(os.path.dirname(self.config['watermark_path']), exist_ok=True)
        
        # Create a default watermark if it doesn't exist
        self._create_default_watermark_if_needed()
        
        # Initialize session ID
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Initialize storage for detailed transcript
        self.full_transcript_with_words: Optional[List[Dict[str, Any]]] = None
        
        # Initialize logger
        self.logger = logging.getLogger("factual")
        
        # Validate required parameters
        self._validate_config()
    
    def _load_config(self, config_path: str) -> None:
        """Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration JSON file
        """
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
                logger.info(f"Loaded configuration from {config_path}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load config from {config_path}: {str(e)}")
            raise
    
    def _validate_config(self) -> None:
        """Validate required configuration parameters."""
        if not self.config['openai_api_key']:
            raise ValueError("OpenAI API key is required. Set it in the config file or OPENAI_API_KEY environment variable.")
        if not self.config['elevenlabs_api_key']:
            raise ValueError("ElevenLabs API key is required. Set it in the config file or ELEVENLABS_API_KEY environment variable.")
            
        # Validate ElevenLabs API key by making a test request
        try:
            logger.info("Validating ElevenLabs API key...")
            response = requests.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": self.config['elevenlabs_api_key']}
            )
            
            if response.status_code == 401:
                raise ValueError(
                    "ElevenLabs API key is invalid or expired. Please check your API key at "
                    "https://elevenlabs.io/app/account and update it in your config file or "
                    "set a valid ELEVENLABS_API_KEY environment variable."
                )
            elif response.status_code == 403:
                raise ValueError(
                    "ElevenLabs API key lacks permission. Your subscription may have expired or "
                    "you're using a key with insufficient privileges."
                )
            elif response.status_code >= 400:
                raise ValueError(
                    f"ElevenLabs API error (HTTP {response.status_code}): {response.text}. "
                    "Check your API key and account status."
                )
                
            response.raise_for_status()
            
            # Verify subscription status
            try:
                user_data = response.json()
                subscription = user_data.get("subscription", {})
                status = subscription.get("status")
                tier = subscription.get("tier")
                
                if status == "expired":
                    raise ValueError(
                        "Your ElevenLabs subscription has expired. Please renew your subscription at "
                        "https://elevenlabs.io/app/subscription"
                    )
                
                character_count = subscription.get("character_count", 0)
                character_limit = subscription.get("character_limit", 0)
                
                if character_limit > 0 and character_count >= character_limit:
                    logger.warning(
                        f"Your ElevenLabs character limit has been reached ({character_count}/{character_limit}). "
                        "TTS generation may fail. Consider upgrading your plan."
                    )
                
                logger.info(f"ElevenLabs API key is valid (Plan: {tier})")
                
            except (ValueError, KeyError) as e:
                logger.warning(f"Could not parse ElevenLabs user data: {str(e)}. Continuing anyway.")
            
        except requests.RequestException as e:
            # If it's just a connection error, log a warning but don't fail completely
            if not isinstance(e, requests.exceptions.HTTPError) or e.response.status_code != 401:
                logger.warning(f"Could not validate ElevenLabs API key: {str(e)}. Continuing anyway.")
    
    def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function
        """
        max_retries = self.config['max_retries']
        retry_delay = self.config['retry_delay']
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All {max_retries} attempts failed.")
                    raise
    
    def _create_sample_video(self, output_path: str, duration: int = 30) -> str:
        """Create a sample video for testing purposes.
        
        Args:
            output_path: Path to save the video
            duration: Duration of the video in seconds
            
        Returns:
            Path to the created video
        """
        logger.info(f"Creating sample test video of {duration} seconds at {output_path}")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            # Create a test pattern video with a counter
            cmd = [
                self.config['ffmpeg_path'],
                "-f", "lavfi",
                "-i", f"testsrc=duration={duration}:size=1080x1920:rate=30",
                "-f", "lavfi",
                "-i", f"sine=frequency=440:duration={duration}",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",  # Needed for compatibility
                "-y",
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully created sample video at: {output_path}")
                return output_path
            else:
                raise FileNotFoundError(f"Failed to create sample video at: {output_path}")
                
        except Exception as e:
            logger.error(f"Error creating sample video: {str(e)}")
            raise

    def download_reel(self, url: str) -> str:
        """Download a Reel from Instagram or Facebook.
        
        Args:
            url: URL of the Instagram or Facebook Reel
            
        Returns:
            Path to the downloaded video file
        """
        # If use_sample_video is enabled, create and return a sample video instead
        if self.config.get('use_sample_video', False):
            logger.info("Using sample video instead of downloading from social media")
            sample_path = str(Path(self.config['temp_dir']) / self.session_id / "reel.mp4")
            return self._create_sample_video(sample_path)
        
        logger.info(f"Downloading reel from: {url}")
        
        # Identify platform
        platform = self._identify_platform(url)
        
        # Validate URL format based on platform
        if platform == 'unknown':
            error_message = f"Invalid URL format: {url}\n"
            error_message += "URL should be in format:\n"
            error_message += "- Instagram: https://www.instagram.com/reel/XXXX or https://www.instagram.com/p/XXXX\n"
            error_message += "- Facebook: https://www.facebook.com/watch?v=XXXX or https://fb.watch/XXXX or https://www.facebook.com/share/v/XXXX or https://www.facebook.com/share/r/XXXX or https://www.facebook.com/username/videos/XXXX"
            logger.error(error_message)
            raise ValueError(error_message)
        
        logger.info(f"Detected platform: {platform}")
        
        output_dir = Path(self.config['temp_dir']) / self.session_id
        os.makedirs(output_dir, exist_ok=True)
        
        output_template = str(output_dir / "reel.%(ext)s")
        
        try:
            cmd = [
                self.config['yt_dlp_path'],
                "--no-warnings",
                "-o", output_template,
                url
            ]
            
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Find the downloaded file
            for file in output_dir.glob("reel.*"):
                if file.suffix in ['.mp4', '.mov', '.mkv']:
                    logger.info(f"Successfully downloaded reel to: {file}")
                    return str(file)
            
            raise FileNotFoundError("Downloaded file not found")
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            logger.error(f"Failed to download reel: {error_msg}")
            
            # Provide more helpful error message based on common issues
            if "Unable to extract" in error_msg or "This video is unavailable" in error_msg:
                additional_info = "\nPossible causes:\n"
                additional_info += "- The content might be private or from a private account\n"
                additional_info += "- The content might have been deleted\n"
                additional_info += "- The URL might be incorrect (must be a direct link to a specific video)\n"
                
                if platform == 'instagram':
                    additional_info += "- Instagram might have changed their API\n\n"
                    additional_info += "Try using a public reel URL like: https://www.instagram.com/reel/XXXX"
                elif platform == 'facebook':
                    additional_info += "- Facebook might have changed their API\n"
                    additional_info += "- Facebook content might require authentication\n\n"
                    additional_info += "Try using a public Facebook video URL like: https://www.facebook.com/watch?v=XXXX"
                
                logger.error(additional_info)
                error_msg += additional_info
                
            raise RuntimeError(f"Failed to download {platform} content: {error_msg}")
    
    def transcribe_audio(self, video_path: str) -> List[Dict[str, Any]]:
        """Transcribe the audio from a video using OpenAI Whisper.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            List of transcription segments with timestamps
        """
        logger.info(f"Transcribing audio from: {video_path}")
        
        import openai
        from openai import OpenAI

        client = OpenAI(api_key=self.config['openai_api_key'])
        
        # Extract audio from video
        audio_path = Path(video_path).with_suffix('.wav')
        
        extract_cmd = [
            self.config['ffmpeg_path'],
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            str(audio_path)
        ]
        
        subprocess.run(extract_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Transcribe using Whisper
        try:
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=self.config['whisper_model'],
                    file=audio_file,
                    response_format="verbose_json"
                )
            
            logger.info(f"Transcription completed, {len(transcription.segments)} segments found")
            
            # Save the transcript for debugging
            transcript_path = Path(audio_path).with_suffix('.json')
            with open(transcript_path, 'w') as f:
                json.dump(transcription.model_dump(), f, indent=2)
            
            # Convert segments to a list of dictionaries
            segments = []
            for segment_data in transcription.segments:
                segment_dict = {
                    'text': segment_data.text,
                    'start': segment_data.start,
                    'end': segment_data.end,
                    'words': [] # Initialize words list
                }
                if hasattr(segment_data, 'words') and segment_data.words:
                    segment_dict['words'] = [
                        {'text': w.word, 'start': w.start, 'end': w.end}
                        for w in segment_data.words
                    ]
                segments.append(segment_dict)
            
            logger.info(f"Processed {len(segments)} segments into dictionaries, including word-level timestamps if available.")
            
            # Store the detailed transcript for later use (e.g., sentence-aware cutting)
            self.full_transcript_with_words = segments
            
            return segments
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise
        finally:
            # Clean up the extracted audio
            if os.path.exists(audio_path):
                os.remove(audio_path)
    
    def extract_claims_and_generate_commentary(self, 
                                             transcript: List[Dict[str, Any]]) -> List[Intervention]:
        """Extract factual claims and generate commentary using GPT-4o.
        
        Args:
            transcript: List of transcription segments with timestamps
            
        Returns:
            List of interventions with commentary
        """
        logger.info("Extracting factual claims and generating commentary")
        
        import openai
        from openai import OpenAI

        client = OpenAI(api_key=self.config['openai_api_key'])
        
        # Prepare the transcript text for analysis
        full_transcript = " ".join([segment['text'] for segment in transcript])
        
        # Function to match generated interventions back to transcript segments
        def map_intervention_to_segments(intervention_text: str, segments: List[Dict[str, Any]]) -> Tuple[float, float, Optional[float]]: # Modified return type
            """Find the start and end timestamps for an intervention and the duration of the original segment.""" # Modified docstring
            # More robust segment mapping
            best_match_segment = None
            best_match_score = 0
            original_segment_duration: Optional[float] = None # Variable to store the duration

            # Clean the intervention text for comparison
            clean_intervention = intervention_text.lower().strip()
            
            # Search each segment for the best match
            for i, segment in enumerate(segments):
                segment_text = segment['text'].lower()
                
                # Try exact substring match first
                if clean_intervention in segment_text:
                    # Found a direct substring match
                    original_segment_duration = segment['end'] - segment['start']
                    return segment['start'], segment['end'], original_segment_duration
                
                # Try partial word matching
                words_in_intervention = set(clean_intervention.split())
                words_in_segment = set(segment_text.split())
                common_words = words_in_intervention.intersection(words_in_segment)
                
                # Calculate a match score based on common words
                if len(words_in_intervention) > 0:
                    match_score = len(common_words) / len(words_in_intervention)
                    
                    # Track the best match
                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_segment = segment
            
            # If we found a decent match (at least 30% of words match)
            if best_match_score >= 0.3 and best_match_segment:
                original_segment_duration = best_match_segment['end'] - best_match_segment['start']
                return best_match_segment['start'], best_match_segment['end'], original_segment_duration
                
            # If no good match, distribute interventions across transcript evenly
            # This ensures we at least get different timestamps for each intervention
            # intervention_count = len(transcript)  # Assumes we'll have roughly as many interventions as segments # This line seems unused
            segment_index = random.randint(0, len(segments) - 1)  # Randomize to avoid all at same position
            
            logger.warning(f"Couldn't find good match for intervention text '{intervention_text[:50]}...'. Using transcript segment {segment_index} for placement. Target duration will be None.")
            # For placement, use the fallback segment's times. Original duration is None as we didn't find a specific match for the claim.
            return segments[segment_index]['start'], segments[segment_index]['end'], None
        
        # Get the character limit from config for the prompt
        max_text_length = self.config.get('max_intervention_text_length', 250)
        
        # Prompt for GPT-4o to identify factual claims and generate commentary
        system_prompt = f"""You are a fact-checking assistant that identifies factual claims in video transcripts 
and provides accurate and neutral commentary. For each factual claim you identify, determine if it is accurate or inaccurate
based on your knowledge (up to your training cutoff date).

For each claim:
1. Classify whether it's a factual claim or just an opinion/subjective statement
2. If it's a factual claim, assess its accuracy
3. Generate a brief, neutral correction for inaccurate claims or confirmation for accurate ones
4. Include credible sources when possible in your commentary

Format your response as a JSON object with an array field named "interventions".
Each intervention should have these fields:
- claim_text: The exact claim from the transcript (≤120 chars)
- intervention_text: Your factual commentary (correction or confirmation) — **~{max_text_length} characters max**
- intervention_type: Either "correction" or "confirmation"
- sources: **array of up to 3 objects**. Each object must have:
    • title – full title of the study/article/report
    • description – detailed description: journal/publication (year), authors/institution, sample size, key finding that supports your intervention
    • url – direct link to the source

Example source object:
{{
  "title": "Measles, Mumps, Rubella Vaccination and Autism — A Nationwide Cohort Study",
  "description": "Annals of Internal Medicine (2019), Denmark study with 657,461 children, found no increased autism risk after MMR vaccination",
  "url": "https://www.acpjournals.org/doi/10.7326/M18-2101"
}}

Keep intervention_text concise – don't embed full citations there.

Only identify meaningful factual claims that can be verified. Ignore opinions, subjective statements, or minor details.
Keep your commentary very concise, neutral, and focused on factual accuracy. The intervention text will be displayed as an overlay, so brevity is essential."""

        user_prompt = f"""Here is the transcript from a social media video that I need you to fact-check. 
Identify all factual claims and provide appropriate commentary.

TRANSCRIPT:
{full_transcript}

Please format your response as a JSON object with an array field named "interventions".
Each intervention should contain:
- claim_text: The exact claim from the transcript
- intervention_text: Your factual commentary (correction or confirmation)
- intervention_type: Either "correction" or "confirmation"
- sources: **array of up to 3 objects**.  Each object must have:
    • description – one-line description of the source (authors/institute, year)
    • url – direct link to the source

Keep the JSON small – don't embed full citations, only short description + URL.

Only include meaningful factual statements that require verification."""

        interventions = []
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Parse the response JSON
            content = response.choices[0].message.content
            logger.info(f"GPT-4o raw response: {content[:100]}...")  # Log the first 100 chars for debugging
            result = json.loads(content)
            
            # For debugging
            logger.info(f"GPT-4o response structure: {list(result.keys())}")
            
            # Extract interventions from various possible response formats
            interventions_data = []
            if "interventions" in result:
                interventions_data = result["interventions"]
                logger.info(f"Found interventions array with {len(interventions_data)} items")
            elif "claim_text" in result and "intervention_text" in result and "intervention_type" in result:
                # Single intervention object
                interventions_data = [result]
                logger.info("Found single intervention object")
            elif isinstance(result, list):
                interventions_data = result
                logger.info(f"Found list with {len(interventions_data)} items")
            else:
                # Look for any key that could contain an array of interventions
                for key, value in result.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict) and "claim_text" in value[0]:
                            interventions_data = value
                            logger.info(f"Found list under key '{key}' with {len(value)} items")
                            break
                
            logger.info(f"Found {len(interventions_data)} interventions in GPT-4o response")
            
            # Evenly distribute interventions if we have more than one
            intervention_count = len(interventions_data)
            
            # Make a copy of the transcript for distribution
            transcript_copy = transcript.copy()
            
            # Distribute interventions evenly throughout the transcript if there are multiple
            # This ensures we don't have all interventions at the same timestamp
            import random
            random.seed(42)  # For reproducibility
            
            # Map each intervention to the transcript segments
            for idx, intervention_data in enumerate(interventions_data):
                # Get claim text from the response
                claim_text = intervention_data["claim_text"]
                
                # Try to find the exact segment that contains this claim
                start_time, end_time, mapped_original_duration = map_intervention_to_segments(claim_text, transcript_copy) # Unpack duration
                
                # Ensure interventions don't all start at the same time if mapping fails
                if idx > 0 and start_time == interventions[idx-1].timestamp_start:
                    # Find a different segment for placement
                    available_segments = [s for s in transcript if s['start'] != start_time]
                    if available_segments:
                        # Take a random segment to ensure distribution
                        segment = random.choice(available_segments)
                        start_time, end_time = segment['start'], segment['end']
                        # If we re-pick a segment for placement due to overlap, the original_duration might no longer be relevant
                        # or well-defined for this new placement. Setting to None.
                        mapped_original_duration = None 
                        logger.warning(f"Intervention {idx} placement adjusted due to timestamp overlap. Target duration set to None.")
                    else: # Should be rare if transcript has multiple segments
                        logger.warning(f"Intervention {idx} could not find an alternative segment to avoid timestamp overlap. Target duration might be affected.")


                # Apply character limit to intervention text (use the same limit we told GPT-4o about)
                original_text = intervention_data["intervention_text"]
                truncated_text = self._truncate_intervention_text(original_text, max_text_length)
                
                # Create the intervention object
                intervention = Intervention(
                    timestamp_start=start_time,
                    timestamp_end=end_time,
                    claim_text=intervention_data["claim_text"],
                    intervention_text=truncated_text,
                    intervention_type=intervention_data["intervention_type"],
                    target_duration=mapped_original_duration,
                    sources=intervention_data.get("sources", [])
                )
                interventions.append(intervention)
                
                # Log the timestamp for debugging
                logger.info(f"Mapped intervention {idx} to timestamp {start_time:.2f}s - {end_time:.2f}s. Original segment duration for TTS: {mapped_original_duration if mapped_original_duration is not None else 'N/A'}")
            
            # Sort interventions by timestamp
            interventions.sort(key=lambda x: x.timestamp_start)
            
            # Limit number of interventions if needed
            max_interventions = self.config.get('max_interventions', 4)
            if len(interventions) > max_interventions:
                logger.info(f"Limiting from {len(interventions)} to {max_interventions} interventions")
                
                # Calculate a score for each intervention to prioritize which to keep
                scored_interventions = []
                for idx, intervention in enumerate(interventions):
                    # Base score: corrections are more important than confirmations
                    base_score = 10 if intervention.intervention_type == "correction" else 5
                    
                    # Add some randomness to avoid always picking the first N
                    random_factor = random.uniform(0.8, 1.2)
                    
                    # Calculate position score for even distribution
                    # Higher score for interventions distributed throughout the video
                    position_ratio = idx / max(1, len(interventions) - 1)  # 0 to 1
                    position_score = 5 * (1 - abs(position_ratio - 0.5) * 2)  # Higher for middle positions
                    
                    total_score = (base_score + position_score) * random_factor
                    scored_interventions.append((intervention, total_score))
                
                # Sort by score, highest first
                scored_interventions.sort(key=lambda x: x[1], reverse=True)
                
                # Take top N interventions
                selected_interventions = [x[0] for x in scored_interventions[:max_interventions]]
                
                # Resort by timestamp
                selected_interventions.sort(key=lambda x: x.timestamp_start)
                interventions = selected_interventions
            
            logger.info(f"Final set: {len(interventions)} factual interventions")
            return interventions
            
        except Exception as e:
            logger.error(f"Claim extraction failed: {str(e)}")
            raise
    
    def generate_tts_narration(self, interventions: List[Intervention]) -> List[Intervention]:
        """Generate TTS narration for interventions using ElevenLabs API.
        
        Args:
            interventions: List of interventions with commentary
            
        Returns:
            Updated list of interventions with audio file paths and durations
        """
        # Identify which interventions need audio generation
        to_generate = [i for i, intervention in enumerate(interventions) 
                      if intervention.audio_file is None or not os.path.exists(intervention.audio_file)]
        
        if not to_generate:
            logger.info("No TTS generation needed - all interventions have audio")
            return interventions
            
        logger.info(f"Generating TTS narration for {len(to_generate)} interventions")
        
        # Validate ElevenLabs API key again before making multiple requests
        try:
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": self.config['elevenlabs_api_key']}
            )
            if response.status_code == 401:
                raise ValueError(
                    "ElevenLabs API key is invalid or expired. Please check your API key and update it."
                )
            response.raise_for_status()
        except requests.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 401:
                logger.error("ElevenLabs API key is unauthorized. Please check your API key.")
                raise ValueError(
                    "ElevenLabs API key is unauthorized. Please check your API key at "
                    "https://elevenlabs.io/app/account and update it in your config."
                )
            elif isinstance(e, requests.exceptions.ConnectionError):
                logger.warning(f"Connection error while validating ElevenLabs API: {str(e)}. Will attempt to continue.")
            else:
                logger.warning(f"Error validating ElevenLabs API: {str(e)}. Will attempt to continue.")
                
        output_dir = Path(self.config['temp_dir']) / self.session_id / "tts"
        os.makedirs(output_dir, exist_ok=True)

        MIN_SPEED = 0.7  # Minimum TTS speed
        MAX_SPEED = 1.5  # Maximum TTS speed (reduced from 2.0 to avoid API errors)
        MIN_TARGET_DURATION = 1.0 # Minimum duration to attempt speed adjustment (increased from 0.1)
        MAX_SPEED_RATIO = 3.0  # If required speed exceeds this, skip speed adjustment

        for idx in to_generate:
            intervention = interventions[idx]
            final_audio_file_path = str(output_dir / f"intervention_{idx}.mp3")
            
            try:
                url = "https://api.elevenlabs.io/v1/text-to-speech/" + self.config['elevenlabs_voice_id']
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": self.config['elevenlabs_api_key']
                }

                # Default voice settings
                voice_settings = {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
                
                # --- Speed Adjustment Logic ---
                attempt_speed_adjustment = False
                calculated_speed = 1.0

                if (self.config.get('enable_tts_speed_adjustment', False) and 
                    intervention.target_duration and intervention.target_duration > MIN_TARGET_DURATION):
                    attempt_speed_adjustment = True
                    logger.info(f"Intervention {idx}: Target duration provided: {intervention.target_duration:.2f}s. Attempting speed adjustment.")

                    # Pass 1: Generate with default speed to get base duration
                    pass1_data = {
                        "text": intervention.intervention_text,
                        "model_id": "eleven_turbo_v2", # Ensure this model is appropriate
                        "voice_settings": {**voice_settings, "speed": 1.0} 
                    }
                    
                    logger.info(f"Intervention {idx} (Pass 1): Generating TTS with speed 1.0 to get base duration.")
                    response_pass1 = requests.post(url, json=pass1_data, headers=headers)
                    response_pass1.raise_for_status()
                    
                    # Save temporarily to get duration
                    temp_pass1_audio_file = str(output_dir / f"intervention_{idx}_pass1_temp.mp3")
                    with open(temp_pass1_audio_file, 'wb') as f:
                        f.write(response_pass1.content)
                    
                    result_pass1 = subprocess.run(
                        [self.config['ffmpeg_path'], "-i", temp_pass1_audio_file, "-f", "null", "-"],
                        stderr=subprocess.PIPE, text=True, check=True
                    )
                    duration_str_pass1 = [line for line in result_pass1.stderr.split('\n') if "Duration" in line][0]
                    duration_parts_pass1 = duration_str_pass1.split("Duration: ")[1].split(",")[0].split(":")
                    base_tts_duration = float(duration_parts_pass1[0]) * 3600 + float(duration_parts_pass1[1]) * 60 + float(duration_parts_pass1[2])
                    logger.info(f"Intervention {idx} (Pass 1): TTS duration at speed 1.0 is {base_tts_duration:.2f}s.")

                    if os.path.exists(temp_pass1_audio_file): # Clean up temporary file
                        os.remove(temp_pass1_audio_file)

                    if base_tts_duration > MIN_TARGET_DURATION: # Avoid division by zero if base_tts_duration is 0
                        calculated_speed = base_tts_duration / intervention.target_duration
                        logger.info(f"Intervention {idx}: Calculated speed factor: {calculated_speed:.2f}")
                        
                        # Check if required speed is reasonable
                        if calculated_speed > MAX_SPEED_RATIO:
                            logger.warning(f"Intervention {idx}: Required speed {calculated_speed:.2f}x is too high (max reasonable: {MAX_SPEED_RATIO}x). Skipping speed adjustment.")
                            calculated_speed = 1.0
                            attempt_speed_adjustment = False
                        elif calculated_speed < MIN_SPEED:
                            logger.warning(f"Intervention {idx}: Required speed {calculated_speed:.2f}x is too low (min: {MIN_SPEED}x). Using minimum speed.")
                            calculated_speed = MIN_SPEED
                        elif calculated_speed > MAX_SPEED:
                            logger.warning(f"Intervention {idx}: Required speed {calculated_speed:.2f}x exceeds maximum ({MAX_SPEED}x). Using maximum speed.")
                            calculated_speed = MAX_SPEED
                        
                        if attempt_speed_adjustment:
                            logger.info(f"Intervention {idx}: Using speed factor: {calculated_speed:.2f}")
                    else:
                        logger.warning(f"Intervention {idx}: Base TTS duration is too short ({base_tts_duration:.2f}s) for speed calculation. Using default speed 1.0.")
                        calculated_speed = 1.0
                        attempt_speed_adjustment = False # Fallback if base duration is too short


                # --- Final TTS Generation ---
                current_speed_to_use = calculated_speed if attempt_speed_adjustment else 1.0
                
                # Clamp speed to safe range to avoid API errors
                current_speed_to_use = max(MIN_SPEED, min(current_speed_to_use, MAX_SPEED))
                
                final_voice_settings = {**voice_settings, "speed": current_speed_to_use}
                
                # Validate text length (ElevenLabs has limits)
                text_to_use = intervention.intervention_text
                if len(text_to_use) > 5000:  # Conservative limit
                    logger.warning(f"Intervention {idx}: Text too long ({len(text_to_use)} chars), truncating to 5000 chars")
                    text_to_use = text_to_use[:4997] + "..."
                
                final_data = {
                    "text": text_to_use,
                    "model_id": "eleven_turbo_v2", 
                    "voice_settings": final_voice_settings
                }

                if attempt_speed_adjustment:
                    logger.info(f"Intervention {idx} (Pass 2): Generating final TTS with adjusted speed {current_speed_to_use:.2f}.")
                else:
                    if not self.config.get('enable_tts_speed_adjustment', False):
                        logger.info(f"Intervention {idx}: TTS speed adjustment is disabled. Generating with default speed 1.0.")
                    else:
                        logger.info(f"Intervention {idx}: Generating TTS with default speed 1.0 (target duration not applicable or base TTS too short).")

                response = requests.post(url, json=final_data, headers=headers)
                
                # Check for specific errors that might indicate speed adjustment issues
                if response.status_code == 400:
                    logger.warning(f"Intervention {idx}: TTS generation failed with 400 error, likely due to speed adjustment. Trying without speed parameter.")
                    # Fallback: try without speed parameter entirely (some APIs/plans don't support it)
                    fallback_voice_settings = {
                        "stability": voice_settings["stability"],
                        "similarity_boost": voice_settings["similarity_boost"],
                        "style": voice_settings["style"],
                        "use_speaker_boost": voice_settings["use_speaker_boost"]
                        # Explicitly omit 'speed' parameter
                    }
                    fallback_data = {
                        "text": text_to_use,  # Use the same validated text
                        "model_id": "eleven_turbo_v2", 
                        "voice_settings": fallback_voice_settings
                    }
                    
                    logger.info(f"Intervention {idx}: Retrying TTS without speed parameter")
                    response = requests.post(url, json=fallback_data, headers=headers)
                    
                response.raise_for_status()
                
                with open(final_audio_file_path, 'wb') as f:
                    f.write(response.content)
                
                # Get actual audio duration using FFmpeg
                result = subprocess.run(
                    [self.config['ffmpeg_path'], "-i", final_audio_file_path, "-f", "null", "-"],
                    stderr=subprocess.PIPE, text=True, check=True
                )
                
                duration_str = [line for line in result.stderr.split('\n') if "Duration" in line][0]
                duration_parts = duration_str.split("Duration: ")[1].split(",")[0].split(":")
                final_duration = float(duration_parts[0]) * 3600 + float(duration_parts[1]) * 60 + float(duration_parts[2])
                
                intervention.audio_file = final_audio_file_path
                intervention.duration = final_duration
                
                # Ensure the video timeline matches the real audio length
                # Extend the end timestamp so later cuts stay in-sync
                try:
                    intervention.timestamp_end = intervention.timestamp_start + final_duration
                except Exception:
                    # In case attributes are missing for some reason, skip the adjustment gracefully.
                    pass
                
                logger.info(f"Generated TTS for intervention {idx}, final duration: {final_duration:.2f}s (used speed: {current_speed_to_use:.2f})")
                if attempt_speed_adjustment:
                    logger.info(f"  Target duration was: {intervention.target_duration:.2f}s, Achieved: {final_duration:.2f}s")

            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg failed for intervention {idx}: {e.stderr}")
                # Decide if we should raise or try to continue without this intervention's audio
                # For now, re-raise to be consistent with previous behavior
                raise
            except requests.exceptions.RequestException as e:
                # Log more detailed error information
                error_details = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_body = e.response.text
                        logger.error(f"ElevenLabs API request failed for intervention {idx}: {error_details}")
                        logger.error(f"Response body: {error_body}")
                    except:
                        logger.error(f"ElevenLabs API request failed for intervention {idx}: {error_details}")
                else:
                    logger.error(f"ElevenLabs API request failed for intervention {idx}: {error_details}")
                raise
            except Exception as e:
                logger.error(f"TTS generation failed for intervention {idx}: {str(e)}")
                logger.error(f"Intervention text length: {len(intervention.intervention_text)} chars")
                logger.error(f"Speed attempted: {current_speed_to_use}")
                raise
        
        return interventions
    
    def create_composite_video(self, 
                              video_path: str, 
                              interventions: List[Intervention]) -> str:
        """Create the composite video with factual interventions.
        
        Args:
            video_path: Path to the original video
            interventions: List of interventions with audio files and durations
            
        Returns:
            Path to the final composite video
        """
        logger.info("Creating composite video with factual interventions")
        
        output_dir = Path(self.config['output_dir']) / self.session_id
        os.makedirs(output_dir, exist_ok=True)
        
        temp_dir = Path(self.config['temp_dir']) / self.session_id / "segments"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create debug directories if debugging is enabled
        debug_frames_dir = output_dir / "debug_frames"
        debug_segments_dir = output_dir / "debug_segments"
        debug_manifest_dir = output_dir
        
        # VALIDATION: First, validate that the video exists and has audio
        if not os.path.exists(video_path):
            logger.error(f"ERROR: Original video file does not exist: {video_path}")
            raise FileNotFoundError(f"Original video not found: {video_path}")
            
        # Check if the video can be read and has audio
        try:
            logger.info(f"Validating original video: {video_path}")
            validation_cmd = [
                self.config['ffmpeg_path'],
                "-i", video_path,
                "-f", "null", "-"
            ]
            
            validation_result = subprocess.run(
                validation_cmd,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if "Audio: " not in validation_result.stderr:
                logger.warning("WARNING: Original video appears to have no audio track")
        except Exception as e:
            logger.error(f"ERROR: Could not validate original video: {str(e)}")
            raise RuntimeError(f"Failed to validate original video: {str(e)}")
        
        # Get video information
        video_info = self._get_video_info(video_path)
        width = video_info['width']
        height = video_info['height']
        duration = video_info['duration']
        
        # ------------------------------------------------------------------
        # GUARANTEE MINIMUM OPENING ORIGINAL SEGMENT
        # ------------------------------------------------------------------
        try:
            opening_min = self.config.get("min_opening_original_duration", 1.0)
            if interventions and opening_min > 0:
                first_intervention = interventions[0]
                if first_intervention.timestamp_start < opening_min:
                    # Shift the first intervention forward to guarantee room for an opening original segment
                    shift_amt = opening_min - first_intervention.timestamp_start
                    logger.info(
                        f"First intervention starts at {first_intervention.timestamp_start:.2f}s, "
                        f"shifting by {shift_amt:.2f}s to guarantee an opening original segment of "
                        f"{opening_min:.2f}s."
                    )

                    # Apply the shift
                    first_intervention.timestamp_start += shift_amt
                    first_intervention.timestamp_end += shift_amt

                    # Ensure we do not exceed video duration
                    if first_intervention.timestamp_end > duration:
                        logger.warning(
                            "After shifting, first intervention would exceed video length. "
                            "Capping its end time to video duration."
                        )
                        first_intervention.timestamp_end = duration

                    # Re-sort interventions in case shift caused re-ordering (unlikely but safe)
                    interventions.sort(key=lambda x: x.timestamp_start)
        except Exception as e:
            logger.warning(f"Failed to enforce min opening original duration: {str(e)}")
        
        # Debug: Extract frame from start of original video
        self._extract_debug_frame(video_path, debug_frames_dir, "original_start", 0.0)
        
        # If there are no interventions, just add the watermark
        if not interventions:
            logger.info("No factual interventions found, adding watermark only")
            output_path = str(output_dir / "factual_output.mp4")
            self._add_watermark(video_path, output_path)
            return output_path
        
        # FIX #1: Validate and fix intervention timestamps
        # Ensure they are in ascending order and don't overlap
        for i, intervention in enumerate(interventions):
            # Ensure we have reasonable start and end times
            if intervention.timestamp_start < 0:
                logger.warning(f"Negative start time for intervention {i}, adjusting to 0")
                intervention.timestamp_start = 0
                
            if intervention.timestamp_end <= intervention.timestamp_start:
                # If end time is before start time, set a reasonable duration (use TTS duration or default 5s)
                if intervention.duration and intervention.duration > 0:
                    intervention.timestamp_end = intervention.timestamp_start + intervention.duration
                else:
                    intervention.timestamp_end = intervention.timestamp_start + 5.0
                logger.warning(f"Fixed intervention {i} end time: {intervention.timestamp_end:.2f}s")
                
            # Cap to video duration
            if intervention.timestamp_end > duration:
                intervention.timestamp_end = duration
                logger.warning(f"Capped intervention {i} end time to video duration: {duration:.2f}s")
        
        # Sort interventions again after fixing timestamps
        interventions.sort(key=lambda x: x.timestamp_start)
        
        # FIX #2: Ensure interventions don't overlap by adjusting start times
        for i in range(1, len(interventions)):
            if interventions[i].timestamp_start < interventions[i-1].timestamp_end:
                # This intervention starts before the previous one ends
                logger.warning(f"Intervention {i} overlaps with previous, adjusting start time")
                interventions[i].timestamp_start = interventions[i-1].timestamp_end
        
        # Initialize sequence tracking for debugging
        sequence_index = 0
        
        # Create an array to hold all segments in the correct sequence
        valid_segments = []
        expected_sequence = []  # For validation
        
        # Track extraction success for diagnostic purposes
        extraction_stats = {
            "original_segments_attempted": 0,
            "original_segments_succeeded": 0,
            "intervention_segments_attempted": 0,
            "intervention_segments_succeeded": 0
        }
        
        # Log total interventions and video info
        logger.info(f"Processing {len(interventions)} interventions in a {duration:.2f}s video")
        logger.info(f"Video dimensions: {width}x{height}")
        
        # Set initial time marker for reading from original video
        current_original_video_read_head = 0.0
        
        # PROCESS: Create segments in alternating original/intervention order
        for i, intervention in enumerate(interventions):
            # Skip if the intervention is after the video ends
            if intervention.timestamp_start >= duration:
                logger.warning(f"Intervention {i} starts after video ends, skipping")
                continue
            
            logger.info(f"\n===== PROCESSING INTERVENTION {i} =====")
            logger.info(f"Timestamp range: {intervention.timestamp_start:.2f}s to {intervention.timestamp_end:.2f}s")
            
            # Debug: Extract frame at intervention start point
            self._extract_debug_frame(video_path, debug_frames_dir, f"intervention_{i}_start", intervention.timestamp_start)
            
            # 1. Original segment - from current_original_video_read_head to END of intervention's claim
            #    (we want the viewer to hear the full claim before the factual overlay)
            original_segment_intended_end = intervention.timestamp_end
            
            # Default cut is at the intended END of the intervention's claim
            adjusted_cut_time_for_original = original_segment_intended_end

            if self.config.get("enable_sentence_aware_cuts", False) and self.full_transcript_with_words:
                sentence_end_ts = self._find_closest_sentence_end_before(
                    target_time=original_segment_intended_end,
                    transcript_with_words=self.full_transcript_with_words,
                    max_lookbehind_seconds=self.config.get("sentence_cut_max_lookbehind", 3.0),
                    min_time_from_start=current_original_video_read_head
                )
                if sentence_end_ts is not None:
                    logger.info(f"Adjusting original segment cut for intervention {i}: from {original_segment_intended_end:.2f}s to sentence end at {sentence_end_ts:.2f}s.")
                    adjusted_cut_time_for_original = sentence_end_ts
                else:
                    logger.info(f"No suitable sentence end found before {original_segment_intended_end:.2f}s for intervention {i}. Using original cut time.")
            
                            # Ensure cut time is not before the current read head and not after intended end
                adjusted_cut_time_for_original = max(adjusted_cut_time_for_original, current_original_video_read_head)
                adjusted_cut_time_for_original = min(adjusted_cut_time_for_original, original_segment_intended_end)

                # Calculate segment duration
                segment_duration = adjusted_cut_time_for_original - current_original_video_read_head
                
                # Ensure minimum segment duration
                min_segment_duration = self.config.get('min_segment_duration', 3.0)
                if segment_duration > 0 and segment_duration < min_segment_duration:
                    # Try to extend the segment to reach minimum duration
                    # We've already preprocessed to merge interventions, but we'll still enforce min duration here
                    needed_extension = min_segment_duration - segment_duration
                    
                    # Check if we can extend within reasonable bounds (don't overlap with next intervention)
                    max_extension = original_segment_intended_end - adjusted_cut_time_for_original
                    if max_extension > 0:
                        extension = min(needed_extension, max_extension)
                        adjusted_cut_time_for_original += extension
                        segment_duration += extension
                        logger.info(f"Extended segment {i} by {extension:.2f}s to reach minimum duration")
                    else:
                        logger.warning(f"Could not extend segment {i} to reach minimum duration")
            
            logger.info(f"\n----- ORIGINAL SEGMENT {i} (Pre-Intervention) -----")
            logger.info(f"Reading from original video at {current_original_video_read_head:.2f}s for {segment_duration:.2f}s (intended end: {original_segment_intended_end:.2f}s, actual cut: {adjusted_cut_time_for_original:.2f}s)")
            
            segment_before_path = str(temp_dir / f"segment_before_{i}.mp4") # Renamed for clarity
            extraction_stats["original_segments_attempted"] += 1
            
            if segment_duration > 0.01: # Only extract if duration is meaningful
                # Add to expected sequence only if we're actually creating the segment
                expected_sequence.append(f"original_{i}")
                segment_success = self._extract_segment_guaranteed(
                    video_path,
                    segment_before_path,
                    current_original_video_read_head,
                    segment_duration
                )
            
                if segment_success:
                    extraction_stats["original_segments_succeeded"] += 1
                    valid_segments.append({
                        "type": "original", 
                        "path": segment_before_path,
                        "debug_index": sequence_index,
                        "src_start": current_original_video_read_head,
                        "src_end": adjusted_cut_time_for_original,
                        "sequence_name": f"original_{i}"
                    })
                    logger.info(f"SUCCESS: Added original segment {i} to sequence ({segment_duration:.2f}s)")
                    
                    # DEBUG: Save original segment for individual inspection
                    self._save_debug_segment(segment_before_path, debug_segments_dir, f"original_{i}", sequence_index)
                    
                    # DEBUG audio, save segment, extract frame (existing code)
                    # ...

                    sequence_index += 1
                else:
                    logger.error(f"FAILURE: Could not extract original segment {i} - this will disrupt the sequence")
            else:
                logger.info(f"Skipping original segment {i} as its duration is too short ({segment_duration:.2f}s).")

            # 2. Intervention segment - black frame with intervention text and audio
            logger.info(f"\n----- INTERVENTION SEGMENT {i} -----")
            # Log intervention details for debugging
            logger.info(f"Intervention {i} data - Text: '{intervention.intervention_text[:50]}...', Duration: {intervention.duration}, Audio Path: {intervention.audio_file}")
            
            black_segment = str(temp_dir / f"black_segment_{i}.mp4")
            extraction_stats["intervention_segments_attempted"] += 1
            
            intervention_success = False
            try:
                logger.info(f"Creating intervention segment {i}...")
                # Extract a freeze-frame of the very end of the preceding original segment to use as
                # the intervention background. We now write the frame as PNG (instead of JPEG) to
                # avoid colour-space issues that caused the previous JPEG extraction to fail on some
                # videos. We also log any FFmpeg errors so failures are visible in the runtime logs.
                frame_path = str(temp_dir / f"bg_frame_{i}.png")
                try:
                    extract_cmd = [
                        self.config['ffmpeg_path'],
                        "-sseof", "-0.1",  # 0.1 s from the end reliably grabs the final frame
                        "-i", segment_before_path,
                        "-vframes", "1",
                        "-y", frame_path
                    ]
                    result = subprocess.run(extract_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.warning(f"Background frame extraction failed for intervention {i}: {result.stderr}")
                    if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
                        frame_path = None
                except Exception as e_extract:
                    logger.warning(f"Exception during background frame extraction for intervention {i}: {e_extract}")
                    frame_path = None

                # REVOLUTIONARY FIX: Use PIL for accurate text rendering instead of FFmpeg drawtext
                # This completely eliminates the text cutoff issues by using proper text measurement
                try:
                    self._create_intervention_frame_with_pil(
                        intervention.intervention_text,
                        width,
                        height, 
                        intervention.duration,
                        black_segment,
                        intervention.audio_file,
                        frame_path  # Pass the extracted background frame
                    )
                    logger.info(f"Successfully created intervention frame with PIL: {black_segment}")
                except Exception as e:
                    logger.warning(f"PIL method failed, falling back to FFmpeg: {e}")
                    # Fallback to original method if PIL fails
                    self._create_black_frame_with_audio(
                        black_segment,
                        intervention.audio_file,
                        intervention.intervention_text,
                        width,
                        height,
                        intervention.duration,
                        intervention_type=intervention.intervention_type,
                        background_image_path=frame_path
                    )
                
                if os.path.exists(black_segment) and os.path.getsize(black_segment) > 0:
                    # Verify the intervention segment has audio
                    audio_check_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", black_segment,
                        "-hide_banner"
                    ]
                    
                    audio_check = subprocess.run(
                        audio_check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # DEBUG: Check audio properties of the intervention segment
                    for line in audio_check.stderr.split('\n'):
                        if "Audio:" in line:
                            logger.info(f"AUDIO INFO (intervention_{i}): {line.strip()}")
                    
                    if "Audio: " in audio_check.stderr:
                        # Add to expected sequence only if successfully created
                        expected_sequence.append(f"intervention_{i}")
                        # Add intervention segment immediately after its corresponding original segment
                        valid_segments.append({
                            "type": "intervention", 
                            "path": black_segment,
                            "debug_index": sequence_index,
                            "intervention_id": i,
                            "duration": intervention.duration,
                            "sequence_name": f"intervention_{i}"
                        })
                        extraction_stats["intervention_segments_succeeded"] += 1
                        intervention_success = True
                        logger.info(f"SUCCESS: Added intervention segment {i} to sequence")
                        
                        # Debug: Save segment for individual inspection
                        self._save_debug_segment(black_segment, debug_segments_dir, f"intervention_{i}", sequence_index)
                        
                        # Debug: Extract frame from intervention
                        self._extract_debug_frame(black_segment, debug_frames_dir, f"intervention_{sequence_index}", 0.5)
                        
                        sequence_index += 1
                    else:
                        logger.warning(f"Intervention {i} has no audio, trying forced audio method")
                        
                        # Try with forced audio using PIL method
                        os.remove(black_segment)
                        try:
                            self._create_intervention_frame_with_pil(
                                intervention.intervention_text,
                                width,
                                height, 
                                intervention.duration,
                                black_segment,
                                intervention.audio_file,
                                frame_path  # Pass the extracted background frame
                            )
                            logger.info(f"Successfully created intervention frame with PIL (forced audio): {black_segment}")
                        except Exception as e:
                            logger.warning(f"PIL method failed, falling back to FFmpeg (forced audio): {e}")
                            self._create_black_frame_with_audio(
                                black_segment,
                                intervention.audio_file,
                                intervention.intervention_text,
                                width,
                                height,
                                intervention.duration,
                                force_audio=True,
                                intervention_type=intervention.intervention_type # Pass intervention_type
                            )
                        
                        if os.path.exists(black_segment) and os.path.getsize(black_segment) > 0:
                            # Add to expected sequence only if successfully created (for forced audio case)
                            if f"intervention_{i}" not in expected_sequence:
                                expected_sequence.append(f"intervention_{i}")
                            valid_segments.append({
                                "type": "intervention", 
                                "path": black_segment,
                                "debug_index": sequence_index,
                                "intervention_id": i,
                                "duration": intervention.duration,
                                "forced_audio": True,
                                "sequence_name": f"intervention_{i}"
                            })
                            extraction_stats["intervention_segments_succeeded"] += 1
                            intervention_success = True
                            logger.info(f"SUCCESS: Added intervention segment {i} with forced audio to sequence")
                            
                            # Debug: Save segment for individual inspection
                            self._save_debug_segment(black_segment, debug_segments_dir, f"intervention_{i}", sequence_index)
                            
                            # Debug: Extract frame from intervention
                            self._extract_debug_frame(black_segment, debug_frames_dir, f"intervention_{sequence_index}", 0.5)
                            
                            sequence_index += 1
                else:
                    logger.error(f"FAILURE: Failed to create intervention segment {i}")
            except Exception as e:
                logger.error(f"ERROR: Error creating intervention segment {i}: {str(e)}")
            
            # Debug: Extract frame at intervention end point
            self._extract_debug_frame(video_path, debug_frames_dir, f"intervention_{i}_end", intervention.timestamp_end)
            
            # Update read head for the *next* original segment to start after the current claim ended in original video
            current_original_video_read_head = intervention.timestamp_end
            logger.info(f"Next original video segment will resume from: {current_original_video_read_head:.2f}s (after intervention {i}'s claim which ended at {intervention.timestamp_end:.2f}s in original video)")
        
        # Add final segment if needed
        if current_original_video_read_head < duration: # duration is total original video duration
            logger.info(f"\n----- FINAL SEGMENT -----")
            
            final_segment_duration = duration - current_original_video_read_head # Renamed for clarity
            logger.info(f"FINAL SEGMENT: from {current_original_video_read_head:.2f}s to {duration:.2f}s (duration: {final_segment_duration:.2f}s)")
            
            final_segment_path = str(temp_dir / "final_segment.mp4") # Renamed for clarity
            extraction_stats["original_segments_attempted"] += 1
            
            if final_segment_duration > 0.01: # Check duration before extracting
                # Add to expected sequence only if we're actually creating the segment
                expected_sequence.append("original_final")
                segment_success = self._extract_segment_guaranteed(
                    video_path,
                    final_segment_path,
                    current_original_video_read_head,
                    final_segment_duration
                )
            
                if segment_success:
                    extraction_stats["original_segments_succeeded"] += 1
                    valid_segments.append({
                        "type": "original", 
                        "path": final_segment_path,
                        "debug_index": sequence_index,
                        "src_start": current_original_video_read_head,
                        "src_end": duration,
                        "is_final": True,
                        "sequence_name": "original_final"
                    })
                    logger.info(f"SUCCESS: Added final original segment to sequence ({final_segment_duration:.2f}s)")
                    
                    # DEBUG: Save final segment for individual inspection
                    self._save_debug_segment(final_segment_path, debug_segments_dir, "original_final", sequence_index)
                    
                    # DEBUG audio, save segment, extract frame (existing code)
                    # ...
                    sequence_index += 1
                else:
                    logger.error(f"FAILURE: Failed to extract final segment")
            else:
                logger.info(f"Skipping final segment as its duration is too short ({final_segment_duration:.2f}s).")

        # Add summary segment if enabled
        if self.config.get('include_summary_frame', True) and interventions:
            logger.info(f"\n----- SUMMARY SEGMENT -----")
            logger.info(f"Creating summary frame for {len(interventions)} interventions")
            
            summary_segment_path = self._create_summary_segment(interventions, width, height)
            
            if summary_segment_path:
                # Add to expected sequence only if we successfully created the segment
                expected_sequence.append("summary")
                valid_segments.append({
                    "type": "summary",
                    "path": summary_segment_path,
                    "debug_index": sequence_index,
                    "sequence_name": "summary"
                })
                logger.info(f"SUCCESS: Added summary segment to sequence")
                
                # DEBUG: Save summary segment for individual inspection
                self._save_debug_segment(summary_segment_path, debug_segments_dir, "summary", sequence_index)
                
                sequence_index += 1
            else:
                logger.warning(f"Failed to create summary segment, continuing without it")

        # VALIDATION: Check the pattern of segments
        logger.info("\n===== SEGMENT SEQUENCE VALIDATION =====")
        
        # Log extraction statistics
        logger.info("\nSegment extraction statistics:")
        logger.info(f"- Original segments attempted: {extraction_stats['original_segments_attempted']}")
        logger.info(f"- Original segments succeeded: {extraction_stats['original_segments_succeeded']}")
        logger.info(f"- Intervention segments attempted: {extraction_stats['intervention_segments_attempted']}")
        logger.info(f"- Intervention segments succeeded: {extraction_stats['intervention_segments_succeeded']}")
        
        # Check if we have matching segments (should be equal or one more original)
        if extraction_stats['original_segments_succeeded'] < extraction_stats['intervention_segments_succeeded']:
            logger.error("ERROR: Fewer original segments than intervention segments - sequence will be incorrect!")
        
        # Verify the sequence is alternating original/intervention
        is_alternating = True
        for i in range(1, len(valid_segments)):
            current_type = valid_segments[i]["type"]
            prev_type = valid_segments[i-1]["type"]
            if current_type == prev_type:
                is_alternating = False
                logger.error(f"ERROR: Sequence is not alternating at position {i}: {prev_type} followed by {current_type}")
        
        if is_alternating:
            logger.info("SUCCESS: Sequence is properly alternating between original and intervention segments")
        
        # VALIDATION: Check the actual sequence against expected sequence
        logger.info("\nExpected sequence:")
        for i, name in enumerate(expected_sequence):
            logger.info(f"  {i+1}. {name}")
            
        logger.info("\nActual sequence:")
        actual_sequence = [s.get("sequence_name", f"{s['type']}_{s['debug_index']}") for s in valid_segments]
        for i, name in enumerate(actual_sequence):
            logger.info(f"  {i+1}. {name}")
        
        # Generate detailed sequence manifest for debugging
        self._write_sequence_manifest(valid_segments, debug_manifest_dir, video_path)
        
        # Check if we have any segments to concatenate
        if not valid_segments:
            logger.error("No valid segments were created, using original video with watermark")
            output_path = str(output_dir / "factual_output.mp4")
            self._add_watermark(video_path, output_path)
            return output_path
        
        # Log the final sequence of segments
        logger.info(f"\nFinal sequence for concatenation ({len(valid_segments)} segments):")
        for i, segment in enumerate(valid_segments):
            logger.info(f"  {i+1}. {segment['type']} segment: {segment['path']} (debug_index: {segment.get('debug_index', 'N/A')})")
        
        # Create concatenation file
        concat_file = str(temp_dir / "concat.txt")
        with open(concat_file, 'w') as f:
            for segment in valid_segments:
                f.write(f"file '{os.path.abspath(segment['path'])}'\n")
        
        # Debug: print contents of concat file
        logger.info(f"\nContents of concat file ({concat_file}):")
        with open(concat_file, 'r') as f:
            concat_contents = f.read()
            logger.info(concat_contents)
        
        # Output path for final video
        output_path = str(output_dir / "factual_output.mp4")
        temp_output = str(temp_dir / "temp_output.mp4")
        
        # FIX: Prepare segments for better audio concat by normalizing audio
        # This step converts all segment audio to consistent format before concatenation
        logger.info("\n===== NORMALIZING AUDIO FOR SEGMENTS =====")
        normalized_segments = []
        
        for i, segment in enumerate(valid_segments):
            orig_path = segment["path"]
            norm_path = f"{orig_path}.norm.mp4"
            
            try:
                # Normalize audio parameters for each segment before concatenation
                # This ensures they all have the same sample rate, channel layout, etc.
                normalize_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", orig_path,
                    "-c:v", "copy",             # Copy video stream unchanged
                    "-c:a", "aac",              # Use AAC codec for audio
                    "-ar", "48000",             # Standard sample rate
                    "-ac", "2",                 # Stereo
                    "-b:a", "192k",             # Good audio quality
                    "-af", "aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11",  # Normalize loudness + resample
                    "-y",
                    norm_path
                ]
                
                logger.info(f"Normalizing audio for segment {i+1}...")
                subprocess.run(normalize_cmd, check=True, capture_output=True)
                
                if os.path.exists(norm_path) and os.path.getsize(norm_path) > 0:
                    # Use the normalized segment instead of the original
                    normalized_segments.append({
                        "type": segment["type"],
                        "path": norm_path,
                        "orig_path": orig_path,
                        "sequence_name": segment.get("sequence_name", "")
                    })
                    logger.info(f"Successfully normalized segment {i+1}")
                else:
                    # Fallback to original if normalization fails
                    normalized_segments.append({
                        "type": segment["type"],
                        "path": orig_path,
                        "sequence_name": segment.get("sequence_name", "")
                    })
                    logger.warning(f"Failed to normalize segment {i+1}, using original")
            except Exception as e:
                logger.warning(f"Error normalizing segment {i+1}: {str(e)}, using original")
                normalized_segments.append({
                    "type": segment["type"],
                    "path": orig_path,
                    "sequence_name": segment.get("sequence_name", "")
                })
        
        # Create updated concat file with normalized segments
        norm_concat_file = str(temp_dir / "concat_norm.txt")
        with open(norm_concat_file, 'w') as f:
            for segment in normalized_segments:
                f.write(f"file '{os.path.abspath(segment['path'])}'\n")
        
        # Concatenate segments - try multiple methods for robust handling
        concat_success = False
        
        # Method 1: Using advanced filter_complex with explicit audio mapping
        # This provides more control over audio transitions
        try:
            logger.info("\n===== CONCATENATING SEGMENTS =====")
            logger.info("Using advanced filter_complex method with explicit audio handling...")
            
            # Build input arguments for each segment
            input_args = []
            for segment in normalized_segments:
                input_args.extend(["-i", segment["path"]])
            
            # Create filter complex for more controlled audio handling
            inputs_count = len(normalized_segments)
            
            # Validate that we have segments to work with
            if inputs_count == 0:
                logger.error("No segments to concatenate in advanced method")
                raise ValueError("No segments provided for concatenation")
                
            # Check each segment exists and has audio before building filter
            missing_segments = []
            for i, segment in enumerate(normalized_segments):
                if not os.path.exists(segment["path"]):
                    missing_segments.append(f"Segment {i}: {segment['path']}")
                    
            if missing_segments:
                logger.error(f"Missing segments for concatenation: {missing_segments}")
                raise FileNotFoundError(f"Missing segments: {missing_segments}")
            
            video_inputs = []
            audio_inputs = []
            
            for i in range(inputs_count):
                video_inputs.append(f"[{i}:v]")
                audio_inputs.append(f"[{i}:a]")
            
            # Create concat expressions with proper spacing for readability
            video_concat = " ".join(video_inputs) + f" concat=n={inputs_count}:v=1:a=0[vout]"
            audio_concat = " ".join(audio_inputs) + f" concat=n={inputs_count}:v=0:a=1[aout]"
            
            filter_complex = f"{video_concat};{audio_concat}"
            
            # Build the FFmpeg command
            advanced_cmd = [
                self.config['ffmpeg_path'],
                *input_args,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ac", "2",          # Force stereo output
                "-ar", "48000",      # Consistent sample rate
                "-y",
                temp_output
            ]
            
            logger.info(f"Running advanced concat command with {inputs_count} segments...")
            logger.debug(f"Filter complex: {filter_complex}")
            
            result = subprocess.run(advanced_cmd, check=True, capture_output=True, text=True)
            
            # Verify the output
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                audio_check_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", temp_output,
                    "-hide_banner"
                ]
                
                audio_check = subprocess.run(
                    audio_check_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Verify audio exists in output
                if "Audio: " in audio_check.stderr:
                    logger.info("SUCCESS: Advanced concat method worked with proper audio")
                    import shutil
                    shutil.copy2(temp_output, output_path)
                    concat_success = True
                else:
                    logger.warning("Advanced concat produced output but without audio")
            else:
                logger.warning("Advanced concat produced no output")
                
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr
            if isinstance(stderr_output, bytes):
                stderr_output = stderr_output.decode('utf-8', errors='ignore')
            elif stderr_output is None:
                stderr_output = 'No stderr'
            logger.warning(f"Advanced concat method failed with exit code {e.returncode}")
            logger.warning(f"FFmpeg stderr: {stderr_output}")
        except Exception as e:
            logger.warning(f"Advanced concat method failed: {str(e)}")
        
        # Method 2: Traditional concat demuxer if first method fails
        if not concat_success:
            try:
                logger.info("Trying traditional concat demuxer method...")
                concat_cmd = [
                    self.config['ffmpeg_path'],
                    "-f", "concat",
                    "-safe", "0",
                    "-i", norm_concat_file,
                    "-c:v", "libx264",  # Re-encode video for consistency
                    "-preset", "medium",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-ac", "2",          # Force stereo
                    "-ar", "48000",      # Consistent sample rate
                    "-y",
                    temp_output
                ]
                
                subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
                
                # Verify output
                if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                    audio_check_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", temp_output,
                        "-hide_banner"
                    ]
                    
                    audio_check = subprocess.run(
                        audio_check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    if "Audio: " in audio_check.stderr:
                        logger.info("SUCCESS: Concat demuxer method worked")
                        import shutil
                        shutil.copy2(temp_output, output_path)
                        concat_success = True
                    else:
                        logger.warning("Concat demuxer produced output without audio")
                else:
                    logger.warning("Concat demuxer produced no output")
                    
            except subprocess.CalledProcessError as e:
                stderr_output = e.stderr
                if isinstance(stderr_output, bytes):
                    stderr_output = stderr_output.decode('utf-8', errors='ignore')
                elif stderr_output is None:
                    stderr_output = 'No stderr'
                logger.warning(f"Concat demuxer failed: {stderr_output}")
        
        # Method 3: Individual segment concatenation as last resort
        if not concat_success:
            try:
                logger.info("Trying segment-by-segment concatenation method...")
                
                # Start with the first segment
                import shutil
                first_segment = normalized_segments[0]["path"]
                shutil.copy2(first_segment, temp_output)
                
                # Append each additional segment one by one
                temp_path = temp_output
                
                for i in range(1, len(normalized_segments)):
                    segment_path = normalized_segments[i]["path"]
                    next_temp = f"{temp_dir}/temp_concat_{i}.mp4"
                    
                    # Concatenate this segment to the current result
                    segment_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", temp_path,
                        "-i", segment_path,
                        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vout];[0:a][1:a]concat=n=2:v=0:a=1[aout]",
                        "-map", "[vout]", 
                        "-map", "[aout]",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",  # Speed over quality for intermediate steps
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-y",
                        next_temp
                    ]
                    
                    logger.info(f"Appending segment {i+1}...")
                    subprocess.run(segment_cmd, check=True, capture_output=True)
                    
                    # Update for next iteration
                    if os.path.exists(next_temp) and os.path.getsize(next_temp) > 0:
                        # Clean up previous temp file
                        if i > 1 and os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                        
                        temp_path = next_temp
                    else:
                        logger.error(f"Failed to append segment {i+1}")
                        break
                
                # Copy final result to output
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    # Verify audio in final output
                    audio_check_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", temp_path,
                        "-hide_banner"
                    ]
                    
                    audio_check = subprocess.run(
                        audio_check_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    if "Audio: " in audio_check.stderr:
                        logger.info("SUCCESS: Segment-by-segment method worked")
                        shutil.copy2(temp_path, output_path)
                        concat_success = True
                    else:
                        logger.warning("Segment-by-segment method produced output without audio")
            except Exception as e:
                logger.warning(f"Segment-by-segment method failed: {str(e)}")
        
        # If all concatenation methods failed, use original video with watermark
        if not concat_success:
            logger.error("All concatenation methods failed, using original video with watermark")
            self._add_watermark(video_path, output_path)
        else:
            # Add watermark to the successful concatenated video
            try:
                logger.info("\n===== ADDING WATERMARK =====")
                watermarked_output = str(output_dir / "factual_output_watermarked.mp4")
                self._add_watermark(output_path, watermarked_output)
                
                # Replace original output with watermarked version
                os.remove(output_path)
                os.rename(watermarked_output, output_path)
                
                logger.info("Successfully added watermark to concatenated video")
            except Exception as e:
                logger.error(f"Failed to add watermark: {str(e)}")
        
        # Clean up temp files
        try:
            # Clean up temporary output
            if os.path.exists(temp_output):
                os.remove(temp_output)
                
            # Clean up normalized segments
            for segment in normalized_segments:
                if "orig_path" in segment and os.path.exists(segment["path"]):
                    os.remove(segment["path"])
                    
            # Clean up intermediate temp files
            for i in range(1, len(normalized_segments)):
                temp_path = f"{temp_dir}/temp_concat_{i}.mp4"
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception:
            pass
        
        logger.info(f"\n===== PROCESS COMPLETE =====")
        logger.info(f"Composite video created at: {output_path}")
        return output_path
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Accurately obtain width/height/duration of the *primary* video stream using ffprobe JSON.
        Falls back to the old heuristic if ffprobe is unavailable.
        """
        try:
            import json as _json
            ffprobe_cmd = [
                self.config['ffmpeg_path'].replace('ffmpeg', 'ffprobe'),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "v:0",
                video_path,
            ]
            result = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = _json.loads(result.stdout)
            if data.get("streams"):
                stream = data["streams"][0]
                width = int(stream.get("width", 1080))
                height = int(stream.get("height", 1920))
                duration = float(stream.get("duration", 0.0))
                # If duration missing from stream, get it from format section
                if duration == 0.0:
                    # call ffprobe with format
                    fmt_cmd = [
                        self.config['ffmpeg_path'].replace('ffmpeg', 'ffprobe'),
                        "-v", "quiet", "-print_format", "json", "-show_format", video_path
                    ]
                    fmt_res = subprocess.run(fmt_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                    fmt_data = _json.loads(fmt_res.stdout)
                    duration = float(fmt_data.get("format", {}).get("duration", 0.0))
                return {"width": width, "height": height, "duration": duration}
        except Exception as e:
            logger.warning(f"ffprobe JSON failed ({str(e)}), falling back to heuristic parser.")
        # --- legacy heuristic fallback ---
        cmd = [self.config['ffmpeg_path'], "-i", video_path, "-f", "null", "-"]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        width = 1080
        height = 1920
        for line in result.stderr.split('\n'):
            if "Video:" in line and "x" in line:
                tokens = line.split()
                for tok in tokens:
                    if 'x' in tok and tok[0].isdigit() and tok[-1].isdigit():
                        try:
                            w, h = map(int, tok.split('x'))
                            # choose the *smallest* resolution seen (skip thumbnails > reel)
                            if w * h < width * height:
                                width, height = w, h
                        except:  # noqa: E722
                            continue
        # duration
        duration = 0.0
        for line in result.stderr.split('\n'):
            if "Duration:" in line:
                try:
                    parts = line.split("Duration: ")[1].split(",")[0].split(":")
                    duration = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
                except:  # noqa: E722
                    duration = 0.0
                break
        return {"width": width, "height": height, "duration": duration or 30.0}
    
    def _extract_segment_guaranteed(self, 
                              input_path: str, 
                              output_path: str, 
                              start_time: float, 
                              duration: float,
                              attempt_index: int = 0) -> bool:
        """Extract a segment from a video with a guaranteed output approach, using several methods if needed.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the output segment
            start_time: Start time in seconds
            duration: Duration in seconds
            attempt_index: Which attempt number this is (for logging)
            
        Returns:
            Boolean indicating success
        """
        # Ensure we have valid start time and duration
        start_time = max(0.0, start_time)
        
        # Don't allow extremely short segments (except when explicitly requested for transitions)
        if duration < 0.1 and attempt_index == 0:
            # For non-transition segments, ensure a reasonable minimum duration
            logger.warning(f"Adjusting very short segment duration from {duration:.2f}s to 1.0s")
            duration = 1.0
        elif duration <= 0:
            logger.error(f"Invalid duration: {duration}")
            return False
            
        logger.info(f"GUARANTEED EXTRACTOR: Attempt {attempt_index + 1} - Extracting {duration:.2f}s segment starting at {start_time:.2f}s")
        
        # For long segments (>5 seconds), use a simpler extraction approach that's more efficient
        if duration > 5.0:
            try:
                logger.info(f"Using efficient method for long segment ({duration:.2f}s)")
                efficient_cmd = [
                    self.config['ffmpeg_path'],
                    "-ss", str(start_time),
                    "-i", input_path,
                    "-t", str(duration),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-y",
                    output_path
                ]
                
                subprocess.run(efficient_cmd, check=True, capture_output=True)
                
                # Verify the output
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    # Check if it has audio
                    verify_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", output_path,
                        "-f", "null", "-"
                    ]
                    
                    verify = subprocess.run(verify_cmd, stderr=subprocess.PIPE, text=True)
                    
                    if "Audio: " in verify.stderr:
                        logger.info(f"SUCCESS: Efficiently extracted long segment ({duration:.2f}s)")
                        return True
            except Exception as e:
                logger.warning(f"Efficient extraction failed: {str(e)}, trying alternative methods")
        
        # First method: Use the direct two-pass approach - most reliable for Instagram content
        try:
            # First pass: Extract raw segment
            temp_output = f"{output_path}.temp.mp4"
            method1_cmd = [
                self.config['ffmpeg_path'],
                "-ss", str(start_time),   # Seek to start time (before input for speed)
                "-i", input_path,         # Input file
                "-t", str(duration),      # Duration to extract
                "-c:v", "libx264",        # Re-encode video (better for accurate cuts)
                "-preset", "ultrafast",   # Use fastest encoding for speed
                "-c:a", "aac",            # Re-encode audio for best compatibility
                "-b:a", "192k",           # Good audio quality
                "-y",                     # Overwrite output
                temp_output
            ]
            
            logger.info(f"Running extraction method 1 (two-pass)...")
            result = subprocess.run(
                method1_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Check if the first pass succeeded
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                # Second pass: Re-encode with careful settings for audio
                final_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", temp_output,
                    "-c:v", "copy",
                    "-c:a", "aac",         
                    "-b:a", "192k",
                    "-af", "volume=1.0",   # Normalize audio volume
                    "-y",
                    output_path
                ]
                
                logger.info(f"First pass succeeded, running second pass...")
                subprocess.run(final_cmd, check=True, capture_output=True)
                
                # Verify the output has audio
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    verify_cmd = [
                        self.config['ffmpeg_path'],
                        "-i", output_path,
                        "-f", "null", "-"
                    ]
                    
                    verify = subprocess.run(verify_cmd, stderr=subprocess.PIPE, text=True)
                    
                    if "Audio: " in verify.stderr:
                        logger.info(f"SUCCESS: Two-pass extraction worked!")
                        # Clean up temp file
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                        return True
                    else:
                        logger.warning(f"Two-pass method produced output without audio")
            else:
                logger.warning(f"First pass failed to produce valid output")
                
        except Exception as e:
            logger.warning(f"Two-pass method failed: {str(e)}")
        
        # Clean up temp file if it exists
        try:
            if os.path.exists(f"{output_path}.temp.mp4"):
                os.remove(f"{output_path}.temp.mp4")
        except Exception:
            pass
            
        # Method 2: Single-pass with accurate seeking (after input for accuracy)
        try:
            method2_cmd = [
                self.config['ffmpeg_path'],
                "-i", input_path,         # Input file
                "-ss", str(start_time),   # Seek to start time (after input for accuracy)
                "-t", str(duration),      # Duration to extract
                "-c:v", "libx264",        # Re-encode video
                "-c:a", "aac",            # Re-encode audio
                "-b:a", "192k",           # Good audio quality
                "-y",                     # Overwrite output
                output_path
            ]
            
            logger.info(f"Running extraction method 2 (accurate seeking)...")
            subprocess.run(method2_cmd, check=True, capture_output=True)
            
            # Verify the output
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                verify_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", output_path,
                    "-f", "null", "-"
                ]
                
                verify = subprocess.run(verify_cmd, stderr=subprocess.PIPE, text=True)
                
                if "Audio: " in verify.stderr:
                    logger.info(f"SUCCESS: Method 2 worked!")
                    return True
                else:
                    logger.warning(f"Method 2 produced output without audio")
        except Exception as e:
            logger.warning(f"Method 2 failed: {str(e)}")
            
        # Method 3: Last resort - use FFmpeg's segment muxer (very reliable but may have slight timing issues)
        try:
            method3_cmd = [
                self.config['ffmpeg_path'],
                "-i", input_path,
                "-f", "segment",
                "-segment_start_time", str(start_time),
                "-segment_time", str(duration),
                "-segment_times", str(start_time),
                "-segment_list", f"{output_path}.list.txt",
                "-reset_timestamps", "1",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0",
                "-y",
                f"{output_path}.seg%03d.mp4"
            ]
            
            logger.info(f"Running extraction method 3 (segment muxer)...")
            subprocess.run(method3_cmd, check=True, capture_output=True)
            
            # Find the segment file
            import glob
            segment_files = glob.glob(f"{output_path}.seg*.mp4")
            
            if segment_files and os.path.exists(segment_files[0]) and os.path.getsize(segment_files[0]) > 0:
                # Rename the first segment to the desired output
                import shutil
                shutil.copy2(segment_files[0], output_path)
                
                # Verify the output
                verify_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", output_path,
                    "-f", "null", "-"
                ]
                
                verify = subprocess.run(verify_cmd, stderr=subprocess.PIPE, text=True)
                
                if "Audio: " in verify.stderr:
                    logger.info(f"SUCCESS: Method 3 worked!")
                    
                    # Clean up segment files
                    for f in segment_files:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                    if os.path.exists(f"{output_path}.list.txt"):
                        try:
                            os.remove(f"{output_path}.list.txt")
                        except Exception:
                            pass
                        
                    return True
                else:
                    logger.warning(f"Method 3 produced output without audio")
        except Exception as e:
            logger.warning(f"Method 3 failed: {str(e)}")
        
        # If we've gotten here, all methods failed
        logger.error(f"FAILURE: All extraction methods failed for segment at {start_time:.2f}s")
        
        # If this is the first attempt, try one more time with a slightly modified start time and duration
        if attempt_index == 0:
            logger.info(f"Trying one last attempt with modified timing...")
            # Sometimes adding a small offset helps with problematic videos
            adjusted_start = max(0, start_time - 0.1)
            adjusted_duration = duration + 0.2  # Add a bit of extra time
            return self._extract_segment_guaranteed(input_path, output_path, adjusted_start, adjusted_duration, 1)
        
        return False
    
    def _create_black_frame_with_audio(self, 
                                      output_path: str, 
                                      audio_path: str, 
                                      text: str,
                                      width: int, 
                                      height: int, 
                                      duration: float,
                                      force_audio: bool = False,
                                      intervention_type: Optional[str] = None,
                                      background_image_path: Optional[str] = None) -> None:
        """Create a black frame with audio and text overlay.
        
        Args:
            output_path: Path to save the output video
            audio_path: Path to the audio file. Can be None or invalid.
            text: Text to overlay on the black frame
            width: Width of the output video
            height: Height of the output video
            duration: Duration in seconds
            force_audio: If True, use additional flags to ensure audio is included (less relevant with new direct mapping)
            intervention_type: Type of intervention ('confirmation', 'correction') for specific watermark
            background_image_path: Path to background image for grayscale conversion and dim overlay
        """
        # CRITICAL FIX: Use the robust iterative text sizing algorithm instead of flawed 2-pass logic
        # This ensures consistent text sizing across ALL intervention segments

        temp_text_file_path = None # Initialize path variable
        draw_text_vf_option = "" # Initialize

        ffmpeg_cmd_parts = [self.config['ffmpeg_path']] # Start building the command
        input_source_definitions = [] # Store definitions for -i flags
        video_filter_stages = []
        current_input_idx = 0

        try:
            # --- Define Inputs ---
            # Input 0: Use last-frame background if provided; otherwise fall back to solid black
            if background_image_path and os.path.exists(background_image_path):
                # Loop the image for the segment duration
                ffmpeg_cmd_parts.extend(["-loop", "1", "-i", background_image_path])
                base_video_filter_input_label = f"[{current_input_idx}:v]"
                current_input_idx += 1

                # Convert to grayscale and dim with semi-transparent overlay
                video_filter_stages.append(
                    f"{base_video_filter_input_label}scale={width}:{height},hue=s=0,drawbox=x=0:y=0:w=iw:h=ih:color=gray@0.4:t=fill[v_bg]"
                )
                current_v_filter_label = "[v_bg]"
            else:
                ffmpeg_cmd_parts.extend(["-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}"])
                base_video_filter_input_label = f"[{current_input_idx}:v]"
                current_input_idx += 1
                current_v_filter_label = base_video_filter_input_label
            
            # Conditionally add text overlay based on configuration
            if self.config.get('render_intervention_text', True):
                # CRITICAL FIX: Use the robust _prepare_text_overlay method for ALL text rendering
                # This ensures consistent font sizing across all intervention segments
                draw_text_vf_option, temp_text_file_path, fontsize_val = self._prepare_text_overlay(text, width, height)
                video_filter_stages.append(f"{current_v_filter_label}{draw_text_vf_option}[v_text_drawn]")
                current_v_filter_label = "[v_text_drawn]"
                logger.info(f"Rendering intervention text for {output_path}")
            else:
                logger.info(f"Skipping intervention text rendering for {output_path} (text rendering disabled)")
                # No text overlay, just use the base video input

            # Input 1 (Optional): Intervention Watermark
            specific_watermark_path_to_use = None
            if intervention_type == "confirmation":
                path_key = 'verified_watermark_path'
                specific_watermark_path_to_use = self.config.get(path_key)
                if not (specific_watermark_path_to_use and os.path.exists(specific_watermark_path_to_use)):
                    logger.warning(f"Verified watermark (\'{path_key}\') not found at \'{specific_watermark_path_to_use}\'. Skipping.")
                    specific_watermark_path_to_use = None
            elif intervention_type == "correction":
                path_key = 'bs_watermark_path'
                specific_watermark_path_to_use = self.config.get(path_key)
                if not (specific_watermark_path_to_use and os.path.exists(specific_watermark_path_to_use)):
                    logger.warning(f"BS watermark (\'{path_key}\') not found at \'{specific_watermark_path_to_use}\'. Skipping.")
                    specific_watermark_path_to_use = None

            if specific_watermark_path_to_use:
                ffmpeg_cmd_parts.extend(["-i", specific_watermark_path_to_use])
                watermark_input_filter_label = f"[{current_input_idx}:v]"
                current_input_idx += 1
                
                # 15% of screen height for intervention watermark (1.5x bigger than previous 10%)
                target_wm_height = int(height * 0.15)  # 15% of screen height for intervention watermark
                max_wm_height = int(height * 0.95)    # Cap at 95% of screen height
                target_wm_height = min(target_wm_height, max_wm_height)
                target_wm_height = max(20, target_wm_height)  # Ensure minimum size
                video_filter_stages.append(f"{watermark_input_filter_label}format=rgba,colorchannelmixer=aa=1.0,scale=w=-2:h={target_wm_height}[v_scaled_iwm];{current_v_filter_label}[v_scaled_iwm]overlay=x=(W-w)/2:y=H-h-H*0.01[v_final_with_iwm]")
                current_v_filter_label = "[v_final_with_iwm]"

            # Add filter_complex to command parts
            ffmpeg_cmd_parts.extend(["-filter_complex", ";".join(video_filter_stages)])

            # Audio handling and final mapping
            audio_path_is_valid = audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
            if audio_path_is_valid:
                ffmpeg_cmd_parts.extend(["-i", audio_path])
                audio_input_map_label = f"[{current_input_idx}:a]"
                # current_input_idx += 1 # Not needed if it's the last input

                # Use both -shortest and an explicit -t to make absolutely sure video and audio end
                # at the same timestamp. In earlier builds we relied solely on -shortest, but we
                # observed that the video stream could out-live the audio by ~1–2 s, causing an
                # A/V desync after concatenation. Providing -t <duration> guarantees the muxer
                # cuts both streams at the exact requested length.
                ffmpeg_cmd_parts.extend([
                    "-map", current_v_filter_label,
                    "-map", f"{current_input_idx}:a",  # Direct mapping without brackets
                    "-c:v", "libx264",
                    "-c:a", "aac", "-b:a", "192k",
                    "-t", str(duration),
                    "-shortest", "-y", output_path
                ])
                logger.info(f"Generating black frame for {output_path} with audio. Watermark: {specific_watermark_path_to_use is not None}. Text: {'file' if temp_text_file_path else 'space'}")
            else:
                ffmpeg_cmd_parts.extend([
                    "-map", current_v_filter_label,
                    "-c:v", "libx264",
                    "-an", "-t", str(duration), 
                    "-y", output_path
                ])
                logger.warning(f"Creating black frame WITHOUT audio for {output_path}. Watermark: {specific_watermark_path_to_use is not None}.")
            
            subprocess.run(ffmpeg_cmd_parts, check=True, capture_output=True)
            
            verify_cmd = [self.config['ffmpeg_path'], "-i", output_path, "-hide_banner"]
            verify_result = subprocess.run(verify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "Audio: " in verify_result.stderr or not audio_path_is_valid:
                logger.info(f"Successfully created black frame: {output_path}")
            else:
                logger.warning(f"Created black frame but audio check is inconclusive or shows missing audio: {output_path}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating black frame (main method). Command: {' '.join(ffmpeg_cmd_parts)}")
            stderr_output = e.stderr
            if isinstance(stderr_output, bytes):
                stderr_output = stderr_output.decode('utf-8', errors='ignore')
            elif stderr_output is None:
                stderr_output = 'Unknown FFmpeg error'
            logger.error(f"FFmpeg stderr: {stderr_output}")
            # Fallback logic with centralized positioning
            logger.info("Attempting fallback method for black frame creation (draws a space as text, no intervention watermark).")
            x_offset_px = text_params['text_x_offset_px']
            target_w_px = text_params['text_width_px']
            draw_text_fallback_segment = f"drawtext=text=' ':fontcolor=white:fontsize={fontsize_val}:x={x_offset_px}:y={text_y_position}:boxw={target_w_px}:line_spacing=20:borderw=2:expansion=none"
            try:
                fallback_cmd_parts = [
                    self.config['ffmpeg_path'],
                    "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}",
                ]
                if audio_path_is_valid:
                    fallback_cmd_parts.extend(["-i", audio_path])
                    fallback_cmd_parts.extend([
                        "-vf", draw_text_fallback_segment,
                        "-c:v", "libx264", 
                        "-c:a", "aac", 
                        "-shortest", 
                        "-y", output_path
                    ])
                else:
                    fallback_cmd_parts.extend([
                        "-vf", draw_text_fallback_segment,
                        "-c:v", "libx264",
                        "-an",
                        "-t", str(duration),
                        "-y", output_path
                    ])
                subprocess.run(fallback_cmd_parts, check=True, capture_output=True)
                logger.info(f"Created black frame with simplified (space text) method: {output_path}")
            except Exception as e2:
                logger.error(f"Fallback method (space text) also failed: {str(e2)}")
                raise
        finally:
            if temp_text_file_path and os.path.exists(temp_text_file_path):
                try:
                    os.remove(temp_text_file_path)
                    logger.info(f"Cleaned up temporary text file: {temp_text_file_path}")
                except Exception as e_clean:
                    logger.warning(f"Failed to clean up temporary text file {temp_text_file_path}: {str(e_clean)}")
    
    def _add_watermark(self, input_path: str, output_path: str) -> None:
        """Add a watermark to a video.
        
        Args:
            input_path: Path to the input video
            output_path: Path to save the output video
        """
        # First check if watermark file exists
        if not os.path.exists(self.config['watermark_path']):
            logger.warning(f"Watermark file not found: {self.config['watermark_path']}, creating default")
            self._create_default_watermark_if_needed()
            # If it still doesn't exist (e.g. PIL failed or not installed), then we can't add a watermark.
            if not os.path.exists(self.config['watermark_path']):
                logger.error(f"Cannot add watermark, file missing and default creation failed: {self.config['watermark_path']}")
                # Copy input to output as if no watermarking was to be done.
                import shutil
                try:
                    shutil.copy2(input_path, output_path)
                    logger.info("Watermark processing skipped, copied input to output.")
                except Exception as e_copy:
                    logger.error(f"Failed to copy input to output during watermark skip: {str(e_copy)}")
                    # Raise if copy fails, as we cannot produce the output
                    raise RuntimeError(f"Failed to produce output video due to watermark copy failure: {str(e_copy)}")
                return

        has_audio = False
        try:
            audio_check_cmd = [
                self.config['ffmpeg_path'],
                "-i", input_path,
                "-hide_banner"
            ]
            audio_check = subprocess.run(audio_check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "Audio: " in audio_check.stderr:
                has_audio = True
                logger.info(f"Input video has audio track for watermarking")
            else:
                logger.warning(f"Input video has no audio track for watermarking")
        except Exception as e:
            logger.warning(f"Failed to check audio in input video for watermarking: {str(e)}")
        
        try:
            # Logo watermark: Scale to 25% of video height (increased by 25%), position slightly lower for better spacing
            filter_complex = (
                "[1:v]scale=w=-2:h=ih*0.25[scaled_wm];"
                "[scaled_wm]format=rgba,colorchannelmixer=aa=1[final_wm];"
                "[0:v][final_wm]overlay=x=(W-w)/2:y=H*0.06"
            )
            
            cmd = [
                self.config['ffmpeg_path'],
                "-i", input_path,
                "-i", self.config['watermark_path'],
                "-filter_complex", filter_complex,
                "-c:v", "libx264",
            ]
            
            if has_audio:
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            else:
                cmd.extend(["-an"])
            
            cmd.extend(["-y", output_path])
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                 logger.info(f"Successfully added watermark with main method.")
            else:
                logger.error(f"Failed to create output file with watermark using main method.")
                raise RuntimeError("Watermark main method failed to produce output.")

        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr
            if isinstance(stderr_output, bytes):
                stderr_output = stderr_output.decode('utf-8', errors='ignore')
            elif stderr_output is None:
                stderr_output = 'Unknown FFmpeg error'
            logger.error(f"Error adding watermark with main method: {stderr_output}")
            try:
                logger.info("Attempting fallback watermark method (simple overlay centered at top).")
                # Apply same scaling as main method and center it properly
                filter_complex_str_fallback = "[1:v]scale=w=-2:h=ih*0.25[scaled_fallback_wm];[0:v][scaled_fallback_wm]overlay=x=(W-w)/2:y=H*0.06"

                fallback_cmd = [
                    self.config['ffmpeg_path'],
                    "-i", input_path,
                    "-i", self.config['watermark_path'],
                    "-filter_complex", filter_complex_str_fallback,
                    "-c:a", "copy", 
                    "-y",
                    output_path
                ]
                
                subprocess.run(fallback_cmd, check=True, capture_output=True)
                logger.info("Successfully added watermark using fallback method centered at top")
            except Exception as e2:
                logger.error(f"Fallback watermark method also failed: {str(e2)}")
                logger.warning(f"Copying original file as final fallback for watermark failure.")
                import shutil
                try:
                    shutil.copy2(input_path, output_path)
                    logger.warning(f"Copied original file as final watermark fallback.")
                except Exception as e_copy_final:
                    logger.error(f"All watermark methods failed, and final copy also failed: {str(e_copy_final)}")
                    raise RuntimeError(f"All watermark methods failed: {str(e_copy_final)}")
    
    def generate_manifest(self, 
                         input_path: str, 
                         output_path: str, 
                         interventions: List[Intervention],
                         metadata: Optional[Dict[str, str]] = None) -> str:
        """Generate a JSON manifest for the processed video.
        
        Args:
            input_path: Path to the original video
            output_path: Path to the output video
            interventions: List of interventions
            metadata: Optional metadata to include (platform, URL, etc.)
            
        Returns:
            Path to the manifest file
        """
        logger.info("Generating manifest file")
        
        # Get video information
        output_info = self._get_video_info(output_path)
        
        # Create manifest
        manifest = {
            "original_video": input_path,
            "final_video": output_path,
            "interventions": [asdict(intervention) for intervention in interventions],
            "total_video_duration": output_info["duration"],
            "processed_at": datetime.now().isoformat()
        }
        
        # Add metadata if provided
        if metadata:
            manifest.update(metadata)
        
        # Save manifest
        manifest_path = str(Path(output_path).with_suffix('.json'))
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Manifest saved to: {manifest_path}")
        return manifest_path
    
    def generate_preview(self, 
                        output_path: str, 
                        interventions: List[Intervention]) -> str:
        """Generate a visual preview with thumbnails showing interventions.
        
        Args:
            output_path: Path to the output video
            interventions: List of interventions
            
        Returns:
            Path to the preview image
        """
        logger.info("Generating visual preview")
        
        if not interventions:
            logger.info("No interventions to preview")
            return ""
        
        output_dir = Path(output_path).parent
        preview_path = str(output_dir / "preview.jpg")
        
        # Create thumbnails for both original content and interventions
        thumbnail_paths = []
        
        # Check if the composite video exists and is valid
        composite_valid = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
        # We'll extract frames from the original video if the composite isn't valid
        original_video_path = None
        try:
            # Try to find the original video path from the output path filename
            original_video_dir = Path(self.config['temp_dir']) / self.session_id
            for file in original_video_dir.glob("reel.*"):
                if file.suffix in ['.mp4', '.mov', '.mkv']:
                    original_video_path = str(file)
                    logger.info(f"Found original video at: {original_video_path}")
                    break
                    
            if not original_video_path:
                logger.warning("Original video not found for preview generation")
        except Exception as e:
            logger.warning(f"Error finding original video: {str(e)}")
            
        # Extract thumbnails for each intervention - from before, during, and after
        for i, intervention in enumerate(interventions):
            # 1. Before intervention (original content)
            before_thumbnail = str(output_dir / f"thumbnail_before_{i}.jpg")
            source_video = output_path if composite_valid else original_video_path
            
            if source_video:
                try:
                    # Extract frame just before the intervention
                    cmd = [
                        self.config['ffmpeg_path'],
                        "-ss", str(max(0, intervention.timestamp_start - 0.5)),  # 0.5s before intervention
                        "-i", source_video,
                        "-vframes", "1",
                        "-y",
                        before_thumbnail
                    ]
                    
                    subprocess.run(cmd, check=True, capture_output=True)
                    
                    if os.path.exists(before_thumbnail) and os.path.getsize(before_thumbnail) > 0:
                        thumbnail_paths.append(before_thumbnail)
                        logger.info(f"Created before-intervention thumbnail {i}")
                except Exception as e:
                    logger.warning(f"Failed to create before-intervention thumbnail {i}: {str(e)}")
            
            # 2. During intervention (black frame with optional text)
            # For this we'll generate a sample black frame, optionally with intervention text
            during_thumbnail = str(output_dir / f"thumbnail_during_{i}.jpg")
            try:
                # Generate a black frame - conditionally add text overlay based on config
                cmd = [
                    self.config['ffmpeg_path'],
                    "-f", "lavfi",
                    "-i", f"color=c=black:s=1080x1920:d=1",  # Default size if not known
                ]
                
                if self.config.get('render_intervention_text', True):
                    # Add text overlay - position at 80% height for consistency with 80% width constraint
                    preview_text_y = 1920 * 0.8  # 80% of default height (1920)
                    preview_x_offset = int(1080 * 0.10)  # 10% offset for 80% width area
                    preview_text_width = int(1080 * 0.80)  # 80% width constraint
                    cmd.extend([
                        "-vf", f"drawtext=text='{intervention.intervention_text}':fontcolor=white:fontsize=48:x={preview_x_offset}:y={preview_text_y}:boxw={preview_text_width}:line_spacing=10:expansion=none",
                    ])
                    logger.info(f"Creating preview thumbnail with text for intervention {i}")
                else:
                    # Just a black frame without text
                    logger.info(f"Creating preview thumbnail without text for intervention {i} (text rendering disabled)")
                
                cmd.extend([
                    "-vframes", "1",
                    "-y",
                    during_thumbnail
                ])
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                if os.path.exists(during_thumbnail) and os.path.getsize(during_thumbnail) > 0:
                    thumbnail_paths.append(during_thumbnail)
                    logger.info(f"Created during-intervention thumbnail {i}")
            except Exception as e:
                logger.warning(f"Failed to create during-intervention thumbnail {i}: {str(e)}")
            
            # 3. After intervention (original content continues)
            after_thumbnail = str(output_dir / f"thumbnail_after_{i}.jpg")
            if source_video:
                try:
                    # Extract frame just after the intervention
                    cmd = [
                        self.config['ffmpeg_path'],
                        "-ss", str(intervention.timestamp_end + 0.5),  # 0.5s after intervention
                        "-i", source_video,
                        "-vframes", "1",
                        "-y",
                        after_thumbnail
                    ]
                    
                    subprocess.run(cmd, check=True, capture_output=True)
                    
                    if os.path.exists(after_thumbnail) and os.path.getsize(after_thumbnail) > 0:
                        thumbnail_paths.append(after_thumbnail)
                        logger.info(f"Created after-intervention thumbnail {i}")
                except Exception as e:
                    logger.warning(f"Failed to create after-intervention thumbnail {i}: {str(e)}")
        
        # Add summary frame thumbnail if summary frame is included
        if self.config.get('include_summary_frame', True) and interventions:
            summary_thumbnail = str(output_dir / "thumbnail_summary.jpg")
            try:
                # Generate a sample summary frame for the thumbnail
                summary_text = self._generate_summary_text(interventions)
                
                # Sanitize text for FFmpeg drawtext - remove problematic characters
                sanitized_text = summary_text.replace(chr(10), ' | ')  # Replace newlines with separators
                # Remove emojis and special characters that cause FFmpeg issues
                import re
                sanitized_text = re.sub(r'[^\w\s\-.,!?()%|]', '', sanitized_text)
                # Escape single quotes for shell
                sanitized_text = sanitized_text.replace("'", "\\'")
                
                # Apply 80% width constraint for consistency
                summary_x_offset = int(1080 * 0.10)  # 10% offset
                summary_text_width = int(1080 * 0.80)  # 80% width
                
                cmd = [
                    self.config['ffmpeg_path'],
                    "-f", "lavfi",
                    "-i", f"color=c=black:s=1080x1920:d=1",
                    "-vf", f"drawtext=text='{sanitized_text}':fontcolor=white:fontsize=32:x={summary_x_offset}:y=(h-text_h)/2:boxw={summary_text_width}:line_spacing=10:expansion=none",
                    "-vframes", "1",
                    "-y",
                    summary_thumbnail
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                if os.path.exists(summary_thumbnail) and os.path.getsize(summary_thumbnail) > 0:
                    thumbnail_paths.append(summary_thumbnail)
                    logger.info("Created summary frame thumbnail")
            except Exception as e:
                logger.warning(f"Failed to create summary thumbnail: {str(e)}")
        
        # If no thumbnails were created, return empty string
        if not thumbnail_paths:
            logger.warning("No thumbnails were created for preview")
            return ""
        
        # Create grid of thumbnails using either ImageMagick or FFmpeg
        try:
            # First try with ImageMagick if available
            cols = min(3, len(thumbnail_paths))
            rows = (len(thumbnail_paths) + cols - 1) // cols
            
            montage_cmd = [
                "montage",
                *thumbnail_paths,
                "-tile", f"{cols}x{rows}",
                "-geometry", "320x568+5+5",
                preview_path
            ]
            
            try:
                subprocess.run(montage_cmd, check=True, capture_output=True)
                logger.info(f"Preview image created with ImageMagick: {preview_path}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning("ImageMagick montage command failed, trying FFmpeg alternative")
                
                # Alternative: Use FFmpeg to create a grid (more limited but works without ImageMagick)
                if len(thumbnail_paths) > 0:
                    # Use the first thumbnail as the base
                    import shutil
                    shutil.copy(thumbnail_paths[0], preview_path)
                    logger.info(f"Simple preview created (single image): {preview_path}")
            
        except Exception as e:
            logger.error(f"Failed to create preview grid: {str(e)}")
            if thumbnail_paths:
                # Just use the first thumbnail as preview
                import shutil
                shutil.copy(thumbnail_paths[0], preview_path)
                logger.info(f"Fallback single image preview created: {preview_path}")
        
        # Clean up thumbnails
        for path in thumbnail_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        
        return preview_path
    
    def process_reel(self, url: str) -> Dict[str, str]:
        """Process a social media video through the entire pipeline.
        
        Args:
            url: URL of the social media video (Instagram or Facebook)
            
        Returns:
            Dictionary with paths to output files
        """
        logger.info(f"Starting processing for content: {url}")
        
        # Reset detailed transcript for this session
        self.full_transcript_with_words = None
        
        # Identify platform
        platform = self._identify_platform(url)
        logger.info(f"Processing {platform} content from URL: {url}")

        # Step 1: Download the video
        video_path = self._execute_with_retry(self.download_reel, url)
        
        # Step 2: Transcribe the audio
        transcript = self._execute_with_retry(self.transcribe_audio, video_path)
        
        # Step 3: Extract claims and generate commentary
        interventions = self._execute_with_retry(self.extract_claims_and_generate_commentary, transcript)
        
        # Step 3.5: Preprocess interventions (merge short segments, adjust for sentence boundaries)
        video_info = self._get_video_info(video_path)
        interventions = self._preprocess_interventions(interventions, video_info["duration"])
        
        # Step 4: Generate TTS narration
        if interventions:
            try:
                # Mark interventions that need TTS regeneration (merged or no audio)
                need_tts_generation = [
                    i for i, intervention in enumerate(interventions) 
                    if intervention.audio_file is None or not os.path.exists(intervention.audio_file)
                ]
                
                if need_tts_generation:
                    logger.info(f"Generating TTS for {len(need_tts_generation)} interventions (new or merged)")
                    interventions = self._execute_with_retry(self.generate_tts_narration, interventions)
                else:
                    logger.info("No interventions need TTS generation")
            except ValueError as e:
                if "ElevenLabs API key is" in str(e):
                    logger.warning(f"Skipping TTS generation due to API key issue: {str(e)}")
                    logger.info("Creating silent audio files as fallback to continue pipeline")
                    
                    # Create directory for fallback audio files
                    output_dir = Path(self.config['temp_dir']) / self.session_id / "tts"
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Create silent audio files for each intervention
                    for i, intervention in enumerate(interventions):
                        silent_audio_path = str(output_dir / f"intervention_{i}.mp3")
                        self._create_silent_audio(silent_audio_path, 5.0)  # Default 5-second silent audio
                        intervention.audio_file = silent_audio_path
                        intervention.duration = 5.0
                else:
                    raise  # Re-raise if it's not an API key issue
        
        # Step 5: Create composite video
        output_path = self._execute_with_retry(self.create_composite_video, video_path, interventions)
        
        # Step 5.5: Generate summary slide PNG (if enabled)
        summary_slide_path = ""
        if self.config.get('generate_summary_slide', True):
            try:
                output_dir = str(Path(output_path).parent)
                summary_slide_path = self._create_summary_slide_png(interventions, output_dir)
                if summary_slide_path:
                    logger.info(f"Summary slide created: {summary_slide_path}")
                else:
                    logger.warning("Summary slide generation failed")
            except Exception as e:
                logger.warning(f"Summary slide generation failed: {str(e)}")
        
        # Step 6: Generate manifest and preview
        metadata = {"source_platform": platform, "source_url": url}
        manifest_path = self._execute_with_retry(self.generate_manifest, video_path, output_path, interventions, metadata)
        preview_path = self._execute_with_retry(self.generate_preview, output_path, interventions)

        # ===== ADD CLOSING FRAME (1 SECOND) =====
        try:
            closing_frame_img = Path("assets/closing_frame.png")
            if closing_frame_img.exists():
                # Match the geometry of the just-rendered video so concat will accept it
                video_info = self._get_video_info(output_path)
                target_w = video_info.get("width", 1080)
                target_h = video_info.get("height", 1920)

                closing_temp_dir = Path(self.config['temp_dir']) / self.session_id
                closing_temp_dir.mkdir(parents=True, exist_ok=True)
                closing_video = str(closing_temp_dir / "closing_frame.mp4")

                # 1. Create a 1-second clip from the PNG WITH a silent stereo track
                create_closing_cmd = [
                    self.config['ffmpeg_path'],
                    "-loop", "1",               # hold the frame
                    "-i", str(closing_frame_img),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:r=48000",  # silent audio
                    "-t", "1",                  # total duration 1 s
                    "-vf", f"scale={target_w}:{target_h},format=yuv420p",
                    "-c:v", "libx264",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",                # stop when the shortest input ends (video)
                    "-pix_fmt", "yuv420p",
                    "-y", closing_video
                ]
                subprocess.run(create_closing_cmd, check=True, capture_output=True)

                # 2. Concatenate the main output and the closing clip (streams now line up)
                concat_file = str(closing_temp_dir / "concat_closing.txt")
                with open(concat_file, "w") as f:
                    f.write(f"file '{os.path.abspath(output_path)}'\n")
                    f.write(f"file '{os.path.abspath(closing_video)}'\n")

                final_with_closing = str(Path(output_path).with_name("factual_output_with_closing.mp4"))
                concat_cmd = [
                    self.config['ffmpeg_path'],
                    "-f", "concat", "-safe", "0",
                    "-i", concat_file,
                    "-c", "copy",
                    "-y", final_with_closing
                ]
                subprocess.run(concat_cmd, check=True, capture_output=True)

                # Replace original output with the new one
                import shutil
                shutil.move(final_with_closing, output_path)
                logger.info("Successfully appended closing frame.")
        except Exception as cf_err:
            logger.warning(f"Failed to append closing frame: {str(cf_err)}")

        # Step 6.5: Write sources.txt
        sources_txt_path = ""
        try:
            sources_txt_path = self._write_sources_file(interventions, str(Path(output_path).parent))
        except Exception as e:
            logger.warning(f"Failed to write sources.txt: {e}")

        return {
            "input_video": video_path,
            "output_video": output_path,
            "manifest": manifest_path,
            "preview": preview_path,
            "summary_slide": summary_slide_path,
            "sources_txt": sources_txt_path,
            "source_platform": platform
        }
        
    def _create_silent_audio(self, output_path: str, duration: float = 5.0) -> None:
        """Create a silent audio file as a fallback for failed TTS.
        
        Args:
            output_path: Path to save the silent audio
            duration: Duration of the silent audio in seconds
        """
        try:
            # Create silent audio using FFmpeg
            cmd = [
                self.config['ffmpeg_path'],
                "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
                "-c:a", "mp3",
                "-y",
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Created silent audio fallback at {output_path}")
            else:
                logger.warning(f"Failed to create silent audio at {output_path}")
        except Exception as e:
            logger.error(f"Error creating silent audio: {str(e)}")

    def _create_default_watermark_if_needed(self):
        """Create a default watermark image if it doesn't exist."""
        if os.path.exists(self.config['watermark_path']):
            return
        
        logger.info(f"Creating default watermark at {self.config['watermark_path']}")
        
        # Create a simple text watermark
        try:
            import numpy as np
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a transparent image
            img = Image.new('RGBA', (200, 200), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw a rectangle with white outline
            draw.rectangle([(20, 20), (180, 180)], outline=(255, 255, 255, 200), width=4)
            
            # Add text
            try:
                font = ImageFont.truetype("Arial", 40)
            except IOError:
                # Use default font if Arial not available
                font = ImageFont.load_default()
            
            draw.text((100, 100), "FACT", fill=(255, 255, 255, 200), font=font, anchor="mm")
            
            # Save the image
            img.save(self.config['watermark_path'])
            logger.info(f"Default watermark created at {self.config['watermark_path']}")
            
        except ImportError:
            # If PIL is not installed, create a simple solid color image
            logger.warning("PIL not installed. Creating a simple watermark.")
            with open(self.config['watermark_path'], 'w') as f:
                f.write("FACTUAL")
            logger.info(f"Simple text watermark created at {self.config['watermark_path']}")

    def _extract_debug_frame(self, video_path: str, output_dir: Path, prefix: str, timestamp: float) -> str:
        """Extract a frame from a video at a specific timestamp for debugging.
        
        Args:
            video_path: Path to the video
            output_dir: Directory to save the frame
            prefix: Prefix for the output filename
            timestamp: Timestamp in seconds to extract the frame
            
        Returns:
            Path to the extracted frame, or empty string if failed
        """
        if not self.config.get('debug_visual_checkpoints', False):
            return ""
            
        # Ensure timestamp is valid
        timestamp = max(0.0, timestamp)
        
        # Create frame output path
        os.makedirs(output_dir, exist_ok=True)
        frame_path = str(output_dir / f"{prefix}_{timestamp:.2f}s.jpg")
        
        try:
            cmd = [
                self.config['ffmpeg_path'],
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                frame_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(frame_path) and os.path.getsize(frame_path) > 0:
                logger.info(f"[DEBUG] Extracted frame at {timestamp:.2f}s: {frame_path}")
                return frame_path
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to extract frame at {timestamp:.2f}s: {str(e)}")
        
        return ""
    
    def _save_debug_segment(self, segment_path: str, output_dir: Path, segment_type: str, index: int) -> str:
        """Copy a segment file to a debug directory for individual inspection.
        
        Args:
            segment_path: Path to the segment file
            output_dir: Directory to save the debug copy
            segment_type: Type of segment (original or intervention)
            index: Index of the segment
            
        Returns:
            Path to the copied segment, or empty string if failed
        """
        if not self.config.get('debug_save_segments', False):
            return ""
            
        # Create debug segments directory
        os.makedirs(output_dir, exist_ok=True)
        debug_path = str(output_dir / f"{segment_type}_{index}.mp4")
        
        try:
            import shutil
            shutil.copy2(segment_path, debug_path)
            logger.info(f"[DEBUG] Saved {segment_type} segment {index}: {debug_path}")
            return debug_path
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to save debug segment: {str(e)}")
        
        return ""
    
    def _write_sequence_manifest(self, sequence: List[Dict], output_dir: Path, video_path: str) -> str:
        """Write a detailed sequence manifest file for debugging.
        
        Args:
            sequence: List of segment details
            output_dir: Directory to save the manifest
            video_path: Path to the original video
            
        Returns:
            Path to the manifest file, or empty string if failed
        """
        if not self.config.get('debug_sequence_manifest', False):
            return ""
            
        # Create detailed manifest
        os.makedirs(output_dir, exist_ok=True)
        manifest_path = str(output_dir / "sequence_manifest.json")
        
        try:
            # Get video information for reference
            video_info = self._get_video_info(video_path)
            
            # Create detailed manifest with extra info
            manifest = {
                "original_video": video_path,
                "video_info": video_info,
                "total_segments": len(sequence),
                "sequence": []
            }
            
            # Add each segment with detailed information
            for i, segment in enumerate(sequence):
                segment_info = {}
                segment_info.update(segment)  # Copy original segment info
                
                # Add extra debug info if available
                try:
                    if os.path.exists(segment["path"]):
                        segment_details = self._get_video_info(segment["path"])
                        segment_info["duration"] = segment_details.get("duration", 0)
                        segment_info["width"] = segment_details.get("width", 0)
                        segment_info["height"] = segment_details.get("height", 0)
                        segment_info["position"] = i + 1
                except Exception:
                    pass
                
                manifest["sequence"].append(segment_info)
            
            # Save manifest
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"[DEBUG] Written sequence manifest: {manifest_path}")
            return manifest_path
        except Exception as e:
            logger.warning(f"[DEBUG] Failed to write sequence manifest: {str(e)}")
        
        return ""

    def _find_closest_sentence_end_before(
        self, 
        target_time: float, 
        transcript_with_words: List[Dict[str, Any]], 
        max_lookbehind_seconds: float = 3.0, 
        min_time_from_start: float = 0.0
    ) -> Optional[float]:
        """
        Find the latest sentence end timestamp that occurs at or before target_time,
        within a lookbehind window, and not before min_time_from_start.
        """
        # Common sentence terminators
        sentence_enders = ('.', '?', '!') 
        
        latest_valid_sentence_end_time: Optional[float] = None

        # Iterate segments in reverse (from latest to earliest)
        for segment_idx in range(len(transcript_with_words) - 1, -1, -1):
            segment = transcript_with_words[segment_idx]

            # Optimization: if the entire segment is too early for the lookbehind window, stop
            if segment['end'] < (target_time - max_lookbehind_seconds):
                break 
            
            # Optimization: if the segment starts after our target_time, it's not relevant for cuts *before* target_time
            if segment['start'] > target_time:
                continue

            if 'words' in segment and segment['words']:
                # Iterate words in reverse within this segment (from end of segment to start)
                for word_idx in range(len(segment['words']) - 1, -1, -1):
                    word_info = segment['words'][word_idx]
                    word_end_ts = word_info['end']
                    word_text = word_info['text'].strip()

                    # Check if this word's end time is a potential candidate
                    if word_end_ts <= target_time and \
                       word_end_ts >= (target_time - max_lookbehind_seconds) and \
                       word_end_ts >= min_time_from_start:
                        
                        # Check if the word ends with a sentence terminator
                        if word_text.endswith(sentence_enders):
                            # This is the latest valid sentence end found so far due to reverse iteration.
                            # We can return immediately as we are looking for the *latest* one.
                            return word_end_ts
        
        # If loop completes without returning, no suitable sentence end was found
        return None

    def _find_closest_sentence_start_after(
        self, 
        target_time: float, 
        transcript_with_words: List[Dict[str, Any]], 
        max_lookahead_seconds: float = 2.0, 
        max_time_to_end: Optional[float] = None
    ) -> Optional[float]:
        """
        Find the earliest sentence start timestamp that occurs at or after target_time,
        within a lookahead window, and not after max_time_to_end.
        
        Args:
            target_time: The target time to search from
            transcript_with_words: Transcript with word-level timestamps
            max_lookahead_seconds: Maximum seconds to look ahead from target_time
            max_time_to_end: Optional maximum end time constraint
            
        Returns:
            Timestamp of closest sentence start, or None if not found
        """
        # Common sentence terminators that indicate the start of a new sentence right after them
        sentence_enders = ('.', '?', '!', '。', '？', '！')
        
        # Start of sentence is either:
        # 1. At the beginning of a segment
        # 2. The word after a word ending with a sentence terminator
        
        earliest_valid_sentence_start: Optional[float] = None
        max_search_time = target_time + max_lookahead_seconds
        
        if max_time_to_end is not None:
            max_search_time = min(max_search_time, max_time_to_end)
        
        # Iterate through segments
        for segment_idx, segment in enumerate(transcript_with_words):
            # Skip segments that end before our target_time
            if segment['end'] < target_time:
                continue
                
            # Skip segments that start after our max search time
            if segment['start'] > max_search_time:
                break
            
            # If segment starts after target_time, it's a potential sentence start
            if segment['start'] >= target_time and segment['start'] <= max_search_time:
                if earliest_valid_sentence_start is None or segment['start'] < earliest_valid_sentence_start:
                    earliest_valid_sentence_start = segment['start']
            
            # Check words within the segment
            if 'words' in segment and segment['words']:
                # We only care about words that might be within our search window
                for word_idx, word_info in enumerate(segment['words']):
                    word_start = word_info['start']
                    
                    # Skip words that start before target_time
                    if word_start < target_time:
                        continue
                        
                    # Stop if we're past our max search time
                    if word_start > max_search_time:
                        break
                    
                    # Check if previous word ended with a sentence terminator
                    if word_idx > 0:
                        prev_word = segment['words'][word_idx - 1]['text'].strip()
                        if any(prev_word.endswith(terminator) for terminator in sentence_enders):
                            # This word is the start of a new sentence
                            if earliest_valid_sentence_start is None or word_start < earliest_valid_sentence_start:
                                earliest_valid_sentence_start = word_start
                    elif word_idx == 0 and word_start >= target_time:
                        # First word of segment (could be sentence start) if after target time
                        if earliest_valid_sentence_start is None or word_start < earliest_valid_sentence_start:
                            earliest_valid_sentence_start = word_start
        
        return earliest_valid_sentence_start

    def _identify_platform(self, url: str) -> str:
        """Identify the platform from the URL.
        
        Args:
            url: URL to identify
            
        Returns:
            Platform identifier: 'instagram', 'facebook', or 'unknown'
        """
        if re.match(r'https?://(www\.)?(instagram\.com)/(p|reel|reels)/[\w-]+/?.*', url):
            return 'instagram'
        elif re.match(r'https?://(www\.)?(facebook\.com|fb\.watch)/(reel|watch|share/[rv]|.+/videos|video\.php).*', url):
            return 'facebook'
        else:
            return 'unknown'

    def _condense_intervention_text_with_ai(self, text: str, max_length: int) -> str:
        """Use OpenAI to intelligently condense intervention text while preserving meaning.
        
        Args:
            text: Original intervention text
            max_length: Maximum allowed character length
            
        Returns:
            Condensed text that fits within the limit
        """
        try:
            import openai
            from openai import OpenAI

            client = OpenAI(api_key=self.config['openai_api_key'])
            
            system_prompt = f"""You are a text condensation assistant. Your task is to rewrite fact-checking intervention text to be more concise while preserving readability and all essential factual information.

Requirements:
- Keep the EXACT same factual accuracy and meaning
- Make it suitable for video overlay display but still easily readable
- Target {max_length} characters or less, but prioritize clarity over strict length
- Use clear, direct language that's easy to understand
- Preserve any source citations if present
- Avoid overly compressed text that becomes hard to read"""

            user_prompt = f"""Please condense this fact-checking intervention text to under {max_length} characters while keeping the same meaning and factual accuracy:

"{text}"

Return only the condensed text, nothing else."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency on this simple task
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=100,  # Should be enough for condensed text
                temperature=0.3  # Lower temperature for more consistent results
            )
            
            condensed_text = response.choices[0].message.content.strip()
            
            # Remove quotes if the AI wrapped the response in them
            if condensed_text.startswith('"') and condensed_text.endswith('"'):
                condensed_text = condensed_text[1:-1]
            
            # Verify it actually fits within the limit
            if len(condensed_text) <= max_length:
                logger.info(f"AI condensed intervention text: {len(text)} -> {len(condensed_text)} chars")
                return condensed_text
            else:
                logger.warning(f"AI condensation still too long ({len(condensed_text)} chars), trying aggressive condensation")
                
                # Try one more time with more aggressive instructions
                aggressive_prompt = f"""URGENT: Condense this fact-checking text to EXACTLY {max_length} characters or less. Be extremely concise but keep the core factual correction/confirmation:

"{text}"

Output format: Just the condensed text, no quotes, under {max_length} characters."""

                retry_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": aggressive_prompt}],
                    max_tokens=80,
                    temperature=0.1
                )
                
                retry_condensed = retry_response.choices[0].message.content.strip()
                if retry_condensed.startswith('"') and retry_condensed.endswith('"'):
                    retry_condensed = retry_condensed[1:-1]
                
                if len(retry_condensed) <= max_length:
                    logger.info(f"Aggressive AI condensation succeeded: {len(text)} -> {len(retry_condensed)} chars")
                    return retry_condensed
                else:
                    logger.warning(f"Even aggressive AI condensation failed ({len(retry_condensed)} chars), falling back to manual truncation")
                
        except Exception as e:
            logger.warning(f"AI condensation failed ({str(e)}), falling back to manual truncation")
        
        # If AI condensation fails, fall back to the original logic
        return self._fallback_truncate_intervention_text(text, max_length)

    def _generate_summary_text(self, interventions: List[Intervention]) -> str:
        """Generate summary text showing key claims and truthfulness score.
        
        Args:
            interventions: List of interventions to summarize
            
        Returns:
            Formatted summary text for display
        """
        if not interventions:
            return "No factual claims were identified in this video."
        
        # Calculate truthfulness score
        confirmations = sum(1 for i in interventions if i.intervention_type == "confirmation")
        total_interventions = len(interventions)
        truthfulness_score = int((confirmations / total_interventions) * 100) if total_interventions > 0 else 0
        
        # Select key claims to display (up to max_summary_claims)
        max_claims = self.config.get('max_summary_claims', 5)
        selected_interventions = interventions[:max_claims]  # Take first N interventions
        
        # Build summary text
        summary_lines = []
        summary_lines.append("FACTUAL CLAIMS SUMMARY")
        summary_lines.append("")  # Empty line for spacing
        
        for i, intervention in enumerate(selected_interventions, 1):
            # Truncate claim text to fit on one line (about 60 characters)
            claim_text = intervention.claim_text
            if len(claim_text) > 60:
                claim_text = claim_text[:57] + "..."
            
            # Choose emoji and status based on intervention type
            if intervention.intervention_type == "confirmation":
                emoji = "✅"
                status = "Confirmed"
            else:  # correction
                emoji = "❌"
                status = "Inaccurate"
            
            summary_lines.append(f"{emoji} {claim_text}")
            summary_lines.append(f"   {status}")
            
            if i < len(selected_interventions):  # Add spacing between claims
                summary_lines.append("")
        
        # Add final spacing and score
        summary_lines.append("")
        summary_lines.append(f"🧾 Truthfulness Score: {truthfulness_score}%")
        
        # Show claim count if we had to truncate
        if len(interventions) > max_claims:
            summary_lines.append(f"   ({len(interventions)} total claims checked)")
        
        return "\n".join(summary_lines)
    
    def _generate_summary_narration_text(self, interventions: List[Intervention]) -> str:
        """Generate narration text for the summary.
        
        Args:
            interventions: List of interventions to summarize
            
        Returns:
            Text suitable for TTS narration
        """
        if not interventions:
            return "No factual claims were identified in this video."
        
        confirmations = sum(1 for i in interventions if i.intervention_type == "confirmation")
        corrections = len(interventions) - confirmations
        total_interventions = len(interventions)
        truthfulness_score = int((confirmations / total_interventions) * 100) if total_interventions > 0 else 0
        
        # Create natural-sounding narration
        if total_interventions == 1:
            if confirmations == 1:
                narration = "This video contained 1 factual claim, which was accurate."
            else:
                narration = "This video contained 1 factual claim, which was inaccurate."
        else:
            narration = f"This video contained {total_interventions} factual claims. "
            
            if confirmations > 0 and corrections > 0:
                narration += f"{confirmations} were accurate and {corrections} were not. "
            elif confirmations == total_interventions:
                narration += "All were accurate. "
            else:
                narration += "None were accurate. "
        
        narration += f"Overall truthfulness score: {truthfulness_score} percent."
        
        return narration
    
    def _generate_summary_slide_bullet_points(self, interventions: List[Intervention]) -> List[str]:
        """Generate 3 concise bullet points for the summary slide.
        
        Args:
            interventions: List of interventions to summarize
            
        Returns:
            List of 3 bullet point strings
        """
        if not interventions:
            return [
                "No factual claims identified",
                "Content appears to be opinion-based", 
                "No fact-checking required"
            ]
        
        confirmations = sum(1 for i in interventions if i.intervention_type == "confirmation")
        corrections = len(interventions) - confirmations
        total_interventions = len(interventions)
        truthfulness_score = int((confirmations / total_interventions) * 100) if total_interventions > 0 else 0
        
        bullet_points = []
        
        # Bullet 1: Claims count and breakdown
        if total_interventions == 1:
            if confirmations == 1:
                bullet_points.append("1 factual claim verified as accurate")
            else:
                bullet_points.append("1 factual claim found to be inaccurate")
        else:
            if confirmations > 0 and corrections > 0:
                bullet_points.append(f"{total_interventions} claims checked: {confirmations} accurate, {corrections} inaccurate")
            elif confirmations == total_interventions:
                bullet_points.append(f"All {total_interventions} factual claims verified as accurate")
            else:
                bullet_points.append(f"All {total_interventions} factual claims found inaccurate")
        
        # Bullet 2: Truthfulness score with color indication
        if truthfulness_score >= 80:
            bullet_points.append(f"HIGH truthfulness score: {truthfulness_score}%")
        elif truthfulness_score >= 50:
            bullet_points.append(f"MODERATE truthfulness score: {truthfulness_score}%")
        else:
            bullet_points.append(f"LOW truthfulness score: {truthfulness_score}%")
        
        # Bullet 3: Most significant finding (if any)
        if interventions:
            # Find the most significant correction or notable claim
            corrections_list = [i for i in interventions if i.intervention_type == "correction"]
            confirmations_list = [i for i in interventions if i.intervention_type == "confirmation"]
            
            if corrections_list:
                # Use first correction as example
                claim_text = corrections_list[0].claim_text
                if len(claim_text) > 60:
                    claim_text = claim_text[:57] + "..."
                bullet_points.append(f"Key issue: {claim_text}")
            elif confirmations_list:
                # Use first confirmation as example
                claim_text = confirmations_list[0].claim_text
                if len(claim_text) > 60:
                    claim_text = claim_text[:57] + "..."
                bullet_points.append(f"Verified claim: {claim_text}")
            else:
                bullet_points.append("Detailed fact-checking completed")
        else:
            bullet_points.append("Comprehensive fact-checking analysis performed")
        
        return bullet_points[:3]  # Ensure we return exactly 3 bullet points
    
    def _create_summary_slide_png(self, interventions: List[Intervention], output_dir: str) -> Optional[str]:
        """Create a summary slide as a PNG image with watermarks and bullet points.
        
        This function is completely independent of the --no-text setting since it creates
        a standalone PNG file for manual addition to reels.
        
        Args:
            interventions: List of interventions to summarize
            output_dir: Directory to save the summary slide
            
        Returns:
            Path to the created PNG file, or None if creation failed
        """
        if not self.config.get('generate_summary_slide', True):
            logger.info("Summary slide generation disabled")
            return None
            
        logger.info("Creating summary slide PNG")
        
        # Get slide dimensions
        width = self.config.get('summary_slide_width', 1080)
        height = self.config.get('summary_slide_height', 1920)
        
        # Generate bullet points
        bullet_points = self._generate_summary_slide_bullet_points(interventions)
        logger.info(f"Generated bullet points: {bullet_points}")
        
        # Calculate truthfulness score for watermark selection
        if interventions:
            confirmations = sum(1 for i in interventions if i.intervention_type == "confirmation")
            truthfulness_score = int((confirmations / len(interventions)) * 100)
        else:
            truthfulness_score = 100  # No false claims found
        
        # Select appropriate truthfulness watermark
        truthfulness_watermark_path = None
        if truthfulness_score >= 50:
            truthfulness_watermark_path = self.config.get('verified_watermark_path')
        else:
            truthfulness_watermark_path = self.config.get('bs_watermark_path')
        
        # Create output path
        slide_path = os.path.join(output_dir, "factual_summary_slide.png")
        
        # Try multiple approaches to ensure text is rendered
        approaches = [
            "pil_advanced",
            "complex_with_textfile",
            "simple_with_inline_text",
            "minimal_fallback"
        ]
        
        for approach in approaches:
            try:
                logger.info(f"Attempting summary slide creation with approach: {approach}")
                success = False
                
                if approach == "pil_advanced":
                    success = self._create_slide_with_pil_advanced(
                        bullet_points, width, height, slide_path, 
                        truthfulness_watermark_path
                    )
                elif approach == "complex_with_textfile":
                    success = self._create_slide_with_textfile(
                        bullet_points, width, height, slide_path, 
                        truthfulness_watermark_path
                    )
                elif approach == "simple_with_inline_text":
                    success = self._create_slide_with_inline_text(
                        bullet_points, width, height, slide_path,
                        truthfulness_watermark_path
                    )
                elif approach == "minimal_fallback":
                    success = self._create_slide_minimal_fallback(
                        bullet_points, width, height, slide_path
                    )
                
                if success and os.path.exists(slide_path) and os.path.getsize(slide_path) > 0:
                    logger.info(f"Successfully created summary slide using {approach}: {slide_path}")
                    return slide_path
                    
            except Exception as e:
                logger.warning(f"Approach {approach} failed: {str(e)}")
                continue
                
        logger.error("All summary slide creation approaches failed")
        return None
    
    def _create_slide_with_pil_advanced(self, bullet_points: List[str], width: int, height: int,
                                       slide_path: str, truthfulness_watermark_path: Optional[str]) -> bool:
        """Create clean summary slide showing truthfulness score and appropriate watermark."""
        try:
            # Create black image
            img = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(img)
            
            # Try to find a good system font
            font_paths = [
                '/System/Library/Fonts/Helvetica.ttc',
                '/System/Library/Fonts/Arial.ttf', 
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/Windows/Fonts/arial.ttf'
            ]
            
            font_path = None
            for path in font_paths:
                if Path(path).exists():
                    font_path = path
                    break
            
            # Create fonts for different elements
            try:
                if font_path:
                    label_font = ImageFont.truetype(font_path, 50)
                    score_font = ImageFont.truetype(font_path, 140)
                else:
                    label_font = ImageFont.load_default()
                    score_font = ImageFont.load_default()
            except:
                label_font = ImageFont.load_default()
                score_font = ImageFont.load_default()
            
            # Extract truthfulness score from bullet points
            truthfulness_score = 0
            for point in bullet_points:
                if "truthfulness score:" in point.lower():
                    # Extract percentage from text like "LOW truthfulness score: 0%"
                    import re
                    match = re.search(r'(\d+)%', point)
                    if match:
                        truthfulness_score = int(match.group(1))
                    break
            
            # Draw "TRUTHFULNESS SCORE" label
            label_text = "TRUTHFULNESS SCORE"
            label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
            label_width = label_bbox[2] - label_bbox[0]
            label_x = (width - label_width) // 2
            label_y = height // 2 - 200
            
            # Draw label with outline
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx != 0 or dy != 0:
                        draw.text((label_x + dx, label_y + dy), label_text, font=label_font, fill='black')
            draw.text((label_x, label_y), label_text, font=label_font, fill='white')
            
            # Draw the score percentage in large text
            score_text = f"{truthfulness_score}%"
            score_bbox = draw.textbbox((0, 0), score_text, font=score_font)
            score_width = score_bbox[2] - score_bbox[0]
            score_x = (width - score_width) // 2
            score_y = height // 2 - 80
            
            # Choose color based on score - green if >80%, red otherwise
            score_color = 'green' if truthfulness_score > 80 else 'red'
            
            # Draw score with thick outline
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    if dx != 0 or dy != 0:
                        draw.text((score_x + dx, score_y + dy), score_text, font=score_font, fill='black')
            draw.text((score_x, score_y), score_text, font=score_font, fill=score_color)
            
            # Save the image
            img.save(slide_path, 'PNG', quality=95)
            self.logger.info(f"Created clean summary slide with {truthfulness_score}% score: {slide_path}")
            
            # Add watermarks - choose based on score
            if truthfulness_score > 80:
                # Use verified watermark
                verified_watermark = self._get_watermark_path('verified')
                if verified_watermark:
                    self._add_watermarks_to_slide(slide_path, verified_watermark)
                else:
                    self._add_watermarks_to_slide(slide_path, truthfulness_watermark_path)
            else:
                # Use BS/correction watermark 
                bs_watermark = self._get_watermark_path('bs')
                if bs_watermark:
                    self._add_watermarks_to_slide(slide_path, bs_watermark)
                else:
                    self._add_watermarks_to_slide(slide_path, truthfulness_watermark_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"PIL advanced method failed: {e}")
            return False
    
    def _get_watermark_path(self, watermark_type: str) -> Optional[str]:
        """Get the path to the appropriate watermark based on type"""
        try:
            if watermark_type == 'verified':
                # Look for verified/factual watermark
                verified_paths = [
                    'assets/factual_logo_watermark.png',
                    'assets/factual/factual_logo_watermark.png'
                ]
                for path in verified_paths:
                    if Path(path).exists():
                        return str(Path(path).absolute())
            elif watermark_type == 'bs':
                # Look for BS/correction watermark  
                bs_paths = [
                    'assets/bs_watermark.png',
                    'assets/factual/bs_watermark.png'
                ]
                for path in bs_paths:
                    if Path(path).exists():
                        return str(Path(path).absolute())
            return None
        except Exception as e:
            self.logger.error(f"Error getting watermark path for {watermark_type}: {e}")
            return None
    
    def _create_slide_with_textfile(self, bullet_points: List[str], width: int, height: int, 
                                   slide_path: str, truthfulness_watermark_path: Optional[str]) -> bool:
        """Create slide using temporary text file approach with better font handling."""
        import tempfile
        import platform
        
        # Create temporary text file with proper formatting
        temp_text_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write("FACT-CHECK SUMMARY\n\n")
                for point in bullet_points:
                    f.write(f"• {point}\n\n")
                temp_text_file = f.name
            
            # Find a suitable font based on platform
            fontfile_path = None
            font_options = []
            
            if platform.system() == "Darwin":  # macOS
                font_options = [
                    "/System/Library/Fonts/Helvetica.ttc",
                    "/System/Library/Fonts/Avenir.ttc", 
                    "/System/Library/Fonts/Arial.ttf",
                    "/Library/Fonts/Arial.ttf",
                    "/System/Library/Fonts/Supplemental/Arial.ttf"
                ]
            elif platform.system() == "Linux":
                font_options = [
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
                ]
            elif platform.system() == "Windows":
                font_options = [
                    "C:\\Windows\\Fonts\\arial.ttf",
                    "C:\\Windows\\Fonts\\Arial.ttf",
                    "C:\\Windows\\Fonts\\calibri.ttf"
                ]
            
            # Find first available font
            for font in font_options:
                if os.path.exists(font):
                    fontfile_path = font
                    logger.info(f"Using font: {fontfile_path}")
                    break
            
            # Build FFmpeg command
            cmd = [
                self.config['ffmpeg_path'],
                "-f", "lavfi",
                "-i", f"color=c=black:s={width}x{height}:d=1"
            ]
            
            # Build filter with or without font
            if fontfile_path:
                # Use fontfile parameter
                text_filter = (
                    f"drawtext=textfile='{temp_text_file}':"
                    f"fontcolor=white:fontsize=42:"
                    f"x=(w-text_w)/2:y=h*0.35:"
                    f"fontfile='{fontfile_path}'"
                )
            else:
                # Try without fontfile (use system default)
                logger.warning("No suitable font file found, using system default")
                text_filter = (
                    f"drawtext=textfile='{temp_text_file}':"
                    f"fontcolor=white:fontsize=42:"
                    f"x=(w-text_w)/2:y=h*0.35"
                )
            
            cmd.extend(["-vf", text_filter])
            cmd.extend([
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                slide_path
            ])
            
            logger.info(f"Creating summary slide with command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg textfile error: {result.stderr}")
                return False
                
            # Check if slide was created successfully
            if os.path.exists(slide_path) and os.path.getsize(slide_path) > 0:
                # Add watermarks in a second pass
                self._add_watermarks_to_slide(slide_path, truthfulness_watermark_path)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in textfile approach: {e}")
            return False
        finally:
            if temp_text_file and os.path.exists(temp_text_file):
                try:
                    os.unlink(temp_text_file)
                except:
                    pass
    
    def _create_slide_with_inline_text(self, bullet_points: List[str], width: int, height: int,
                                      slide_path: str, truthfulness_watermark_path: Optional[str]) -> bool:
        """Create slide with inline text using multiple draw commands."""
        import platform
        
        # Find a suitable font based on platform
        fontfile_path = None
        font_options = []
        
        if platform.system() == "Darwin":  # macOS
            font_options = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/Avenir.ttc", 
                "/System/Library/Fonts/Arial.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"
            ]
        elif platform.system() == "Linux":
            font_options = [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
            ]
        elif platform.system() == "Windows":
            font_options = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\Arial.ttf",
                "C:\\Windows\\Fonts\\calibri.ttf"
            ]
        
        # Find first available font
        for font in font_options:
            if os.path.exists(font):
                fontfile_path = font
                logger.info(f"Using font for inline text: {fontfile_path}")
                break
        
        # First create the base image with text
        cmd = [
            self.config['ffmpeg_path'],
            "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d=1"
        ]
        
        # Build a single text block with all content
        text_content = "FACT-CHECK SUMMARY\\n\\n"
        for point in bullet_points:
            # Escape special characters more carefully
            escaped_point = point.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:")
            text_content += f"• {escaped_point}\\n\\n"
        
        # Create the text filter with proper positioning
        y_position = int(height * 0.35)
        
        if fontfile_path:
            text_filter = (
                f"drawtext=text='{text_content}':"
                f"fontcolor=white:fontsize=42:"
                f"x=(w-text_w)/2:y={y_position}:"
                f"fontfile='{fontfile_path}'"
            )
        else:
            logger.warning("No suitable font file found for inline text, using system default")
            text_filter = (
                f"drawtext=text='{text_content}':"
                f"fontcolor=white:fontsize=42:"
                f"x=(w-text_w)/2:y={y_position}"
            )
        
        cmd.extend(["-vf", text_filter])
        cmd.extend([
            "-frames:v", "1",
            "-q:v", "2", 
            "-y",
            slide_path
        ])
        
        logger.info(f"Creating inline text slide with command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg inline text error: {result.stderr}")
            return False
            
        # Check if slide was created and add watermarks
        if os.path.exists(slide_path) and os.path.getsize(slide_path) > 0:
            self._add_watermarks_to_slide(slide_path, truthfulness_watermark_path)
            return True
        
        return False
    
    def _add_watermarks_to_slide(self, slide_path: str, truthfulness_watermark_path: Optional[str]) -> None:
        """Add watermarks to an existing slide image."""
        try:
            temp_output = f"{slide_path}.temp.png"
            
            # Build command
            cmd = [self.config['ffmpeg_path'], "-i", slide_path]
            filter_parts = []
            current_input_idx = 0
            current_v_label = "[0:v]"
            
            # Add ONLY the truthfulness watermark (no main logo to avoid duplicates)
            # The main logo is already in the background of our PIL-generated slide
            
            # Add truthfulness watermark in lower third to avoid text overlap
            if truthfulness_watermark_path and os.path.exists(truthfulness_watermark_path):
                cmd.extend(["-i", truthfulness_watermark_path])
                current_input_idx += 1
                truth_height = int(1920 * 0.12)  # Slightly smaller
                filter_parts.append(
                    f"[{current_input_idx}:v]scale=-2:{truth_height}[truth];"
                    f"{current_v_label}[truth]overlay=x=(W-w)/2:y=H*0.70[v_final]"  # 70% from top (lower third)
                )
                current_v_label = "[v_final]"
            
            if filter_parts:
                cmd.extend(["-filter_complex", ";".join(filter_parts)])
                cmd.extend(["-map", current_v_label])
            else:
                cmd.extend(["-c", "copy"])
            
            cmd.extend([
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                temp_output
            ])
            
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0 and os.path.exists(temp_output):
                os.replace(temp_output, slide_path)
                logger.info("Successfully added watermarks to slide")
            else:
                logger.warning(f"Failed to add watermarks: {result.stderr}")
                    
        except Exception as e:
            logger.warning(f"Failed to add watermarks to slide: {e}")
    
    def _create_summary_segment(self, interventions: List[Intervention], width: int, height: int) -> Optional[str]:
        """Create a summary segment showing claims and truthfulness score.
        
        Args:
            interventions: List of interventions to summarize
            width: Video width
            height: Video height
            
        Returns:
            Path to the created summary segment, or None if creation failed
        """
        if not self.config.get('include_summary_frame', True):
            return None
            
        if not interventions:
            logger.info("No interventions to summarize, skipping summary frame")
            return None
        
        logger.info(f"Creating summary frame for {len(interventions)} interventions")
        
        # Generate summary text
        summary_text = self._generate_summary_text(interventions)
        
        # Generate optional TTS narration
        summary_audio_path = None
        duration = self.config.get('summary_frame_duration', 8.0)
        
        try:
            # Try to generate TTS for the summary
            narration_text = self._generate_summary_narration_text(interventions)
            
            # Create TTS output path
            output_dir = Path(self.config['temp_dir']) / self.session_id / "tts"
            os.makedirs(output_dir, exist_ok=True)
            summary_audio_path = str(output_dir / "summary_narration.mp3")
            
            # Generate TTS
            url = "https://api.elevenlabs.io/v1/text-to-speech/" + self.config['elevenlabs_voice_id']
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.config['elevenlabs_api_key']
            }
            
            voice_settings = {
                "stability": 0.5,
                "similarity_boost": 0.5,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 1.0
            }
            
            data = {
                "text": narration_text,
                "model_id": "eleven_turbo_v2",
                "voice_settings": voice_settings
            }
            
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            with open(summary_audio_path, 'wb') as f:
                f.write(response.content)
            
            # Get actual audio duration
            result = subprocess.run(
                [self.config['ffmpeg_path'], "-i", summary_audio_path, "-f", "null", "-"],
                stderr=subprocess.PIPE, text=True, check=True
            )
            
            duration_str = [line for line in result.stderr.split('\n') if "Duration" in line][0]
            duration_parts = duration_str.split("Duration: ")[1].split(",")[0].split(":")
            duration = float(duration_parts[0]) * 3600 + float(duration_parts[1]) * 60 + float(duration_parts[2])
            
            logger.info(f"Generated summary TTS narration ({duration:.2f}s)")
            
        except Exception as e:
            logger.warning(f"Failed to generate summary TTS: {str(e)}, using silent audio")
            # Create silent audio as fallback
            try:
                output_dir = Path(self.config['temp_dir']) / self.session_id / "tts"
                os.makedirs(output_dir, exist_ok=True)
                summary_audio_path = str(output_dir / "summary_silent.mp3")
                duration = self.config.get('summary_frame_duration', 8.0)
                self._create_silent_audio(summary_audio_path, duration)
                logger.info(f"Created silent audio for summary frame ({duration:.2f}s)")
            except Exception as e2:
                logger.warning(f"Failed to create silent audio: {str(e2)}")
                summary_audio_path = None
                duration = self.config.get('summary_frame_duration', 8.0)
        
        # Create summary segment
        segment_id = str(uuid.uuid4())[:8]
        segment_dir = os.path.join(self.config['temp_dir'], self.session_id, "segments")
        os.makedirs(segment_dir, exist_ok=True)
        output_path = os.path.join(segment_dir, f"summary_segment_{segment_id}.mp4")
        
        try:
            # Force text rendering for summary frame (override --no-text setting)
            original_text_setting = self.config.get('render_intervention_text', True)
            if not original_text_setting:
                logger.info(f"Force-rendering text for {output_path} (overriding --no-text setting)")
                
            # For summary frame, determine watermark based on truthfulness score
            confirmations = sum(1 for i in interventions if i.intervention_type == "confirmation")
            corrections = len(interventions) - confirmations
            truthfulness_score = int((confirmations / len(interventions)) * 100) if len(interventions) > 0 else 0
            
            # Choose watermark based on overall truthfulness
            summary_watermark_path = None
            if truthfulness_score >= 50:
                # Mostly accurate content - use verified watermark if available
                summary_watermark_path = self.config.get('verified_watermark_path')
                logger.info(f"Summary frame will use verified watermark (score: {truthfulness_score}%)")
            else:
                # Mostly inaccurate content - use correction watermark if available  
                summary_watermark_path = self.config.get('bs_watermark_path')
                logger.info(f"Summary frame will use correction watermark (score: {truthfulness_score}%)")
            
            # Validate watermark path
            if summary_watermark_path and not os.path.exists(summary_watermark_path):
                logger.warning(f"Summary watermark not found at {summary_watermark_path}, using no watermark")
                summary_watermark_path = None
                
            # Create summary segment with special handling
            success = self._create_summary_segment_with_watermarks(
                output_path=output_path,
                text=summary_text,
                width=width,
                height=height,
                duration=duration,
                audio_path=summary_audio_path,
                watermark_path=summary_watermark_path,
                force_text_render=True
            )
            
            if success:
                logger.info(f"Successfully created summary segment with both watermarks: {output_path}")
                return output_path
            else:
                logger.error("Failed to create summary segment")
                return None
                
        except Exception as e:
            logger.error(f"Error creating summary segment: {str(e)}")
            return None

    def _create_summary_segment_with_watermarks(self, output_path: str, text: str, width: int, height: int, 
                                               duration: float, audio_path: Optional[str] = None,
                                               watermark_path: Optional[str] = None, 
                                               force_text_render: bool = False) -> bool:
        """Create a summary segment with special handling for watermarks and text.
        
        Args:
            output_path: Path to save the output video
            text: Text to display
            width: Video width
            height: Video height
            duration: Duration in seconds
            audio_path: Optional path to audio file
            watermark_path: Optional path to watermark image
            force_text_render: Force text rendering even if disabled globally
            
        Returns:
            Boolean indicating success
        """
        try:
            # Temporarily override text rendering setting if needed
            original_text_setting = self.config.get('render_intervention_text', True)
            if force_text_render and not original_text_setting:
                self.config['render_intervention_text'] = True
                
            # REVOLUTIONARY FIX: Use the PNG summary slide instead of text rendering
            try:
                # First, create the summary slide PNG
                temp_png_path = output_path.replace('.mp4', '_slide.png')
                
                # Extract bullet points for the PNG slide
                bullet_points = []
                
                # Parse the summary text to extract truthfulness score and key info
                lines = text.split('\n')
                claim_count = 0
                truthfulness_line = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Count claims (lines with emoji)
                    if line.startswith('✅') or line.startswith('❌'):
                        claim_count += 1
                    
                    # Find truthfulness score line
                    elif 'Truthfulness Score:' in line:
                        truthfulness_line = line.replace('🧾 ', '').replace('   ', '')
                
                # Create simplified bullet points for our clean design
                if claim_count > 0:
                    if claim_count == 1:
                        bullet_points.append('1 factual claim found inaccurate' if 'inaccurate' in text.lower() else '1 factual claim confirmed')
                    else:
                        # Count accurate vs inaccurate
                        accurate_count = text.count('✅')
                        inaccurate_count = text.count('❌') 
                        
                        if inaccurate_count > accurate_count:
                            bullet_points.append(f'All {claim_count} factual claims found inaccurate')
                        elif accurate_count > inaccurate_count:
                            bullet_points.append(f'All {claim_count} factual claims confirmed')
                        else:
                            bullet_points.append(f'{claim_count} factual claims analyzed')
                
                # Add truthfulness score
                if truthfulness_line:
                    # Format as needed for our design
                    if 'Truthfulness Score: 0%' in truthfulness_line:
                        bullet_points.append('LOW truthfulness score: 0%')
                    elif 'Truthfulness Score: 100%' in truthfulness_line:
                        bullet_points.append('HIGH truthfulness score: 100%')
                    else:
                        bullet_points.append(truthfulness_line.replace('Truthfulness Score:', 'truthfulness score:'))
                
                # Add a key issue if we have claims
                if claim_count > 0 and 'inaccurate' in text.lower():
                    # Extract first claim for "Key issue"
                    for line in lines:
                        if line.strip().startswith('❌'):
                            claim_preview = line.replace('❌ ', '').strip()
                            if len(claim_preview) > 60:
                                claim_preview = claim_preview[:57] + '...'
                            bullet_points.append(f'Key issue: {claim_preview}')
                            break
                
                # Fallback if no bullet points extracted
                if not bullet_points:
                    bullet_points = [
                        'Factual analysis complete',
                        'Truthfulness score calculated',
                        'Review recommended'
                    ]
                
                # Create the PNG slide using our beautiful PIL method
                png_success = self._create_slide_with_pil_advanced(
                    bullet_points, width, height, temp_png_path, watermark_path
                )
                
                if png_success and os.path.exists(temp_png_path):
                    # Convert PNG to video with audio
                    if audio_path and os.path.exists(audio_path):
                        cmd = [
                            'ffmpeg', '-y',
                            '-loop', '1',
                            '-i', temp_png_path,
                            '-i', audio_path,
                            '-c:v', 'libx264',
                            '-c:a', 'aac',
                            '-shortest',
                            '-pix_fmt', 'yuv420p',
                            output_path
                        ]
                    else:
                        # No audio - create silent video
                        cmd = [
                            'ffmpeg', '-y',
                            '-loop', '1',
                            '-i', temp_png_path,
                            '-t', str(duration),
                            '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p',
                            output_path
                        ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        success = True
                        logger.info(f"Successfully created summary segment from PNG slide: {output_path}")
                        # Clean up temporary PNG
                        try:
                            os.remove(temp_png_path)
                        except:
                            pass
                    else:
                        raise Exception(f"FFmpeg failed: {result.stderr}")
                else:
                    raise Exception("Failed to create PNG slide")
                    
            except Exception as e:
                logger.warning(f"PNG slide method failed for summary, falling back to text rendering: {e}")
                # Use the main FactualPipeline's black frame creation method as fallback
                success = self._create_black_frame_with_audio(
                    output_path=output_path,
                    audio_path=audio_path,
                    text=text,
                    width=width,
                    height=height,
                    duration=duration,
                    force_audio=False,
                    intervention_type=None  # No specific intervention type for summary
                )
            
            # Restore original text setting
            if force_text_render and not original_text_setting:
                self.config['render_intervention_text'] = original_text_setting
                
            # Skip additional watermarking for summary segments 
            # Our PNG slide already has the appropriate watermarks embedded
            # Adding the main logo watermark would create duplicates
            logger.info("Skipping main watermark for summary segment (already embedded in PNG)")
                    
            return success
            
        except Exception as e:
            logger.error(f"Error in summary segment creation: {str(e)}")
            return False

    def _fallback_truncate_intervention_text(self, text: str, max_length: int) -> str:
        """Fallback method to truncate intervention text using simple rules.
        
        Args:
            text: Original intervention text
            max_length: Maximum allowed character length
            
        Returns:
            Truncated text that fits within the limit
        """
        # Try to truncate at sentence boundaries first
        sentences = text.split('. ')
        if len(sentences) > 1:
            truncated = ""
            for sentence in sentences:
                # Check if adding this sentence would exceed the limit
                test_text = truncated + sentence + ". " if truncated else sentence + ". "
                if len(test_text.strip()) <= max_length:
                    truncated = test_text.strip()
                else:
                    break
            
            if truncated and len(truncated) > max_length // 2:  # Only use if we got a reasonable amount
                logger.info(f"Truncated intervention text at sentence boundary: {len(text)} -> {len(truncated)} chars")
                return truncated
        
        # Fall back to word boundaries
        words = text.split()
        truncated_words = []
        current_length = 0
        
        for word in words:
            # Account for space between words (except for the first word)
            word_length = len(word) + (1 if truncated_words else 0)
            
            if current_length + word_length <= max_length:
                truncated_words.append(word)
                current_length += word_length
            else:
                break
        
        if truncated_words:
            truncated_text = " ".join(truncated_words)
            logger.info(f"Truncated intervention text at word boundary: {len(text)} -> {len(truncated_text)} chars")
            return truncated_text
        
        # Last resort: hard truncate (should rarely happen)
        truncated_text = text[:max_length].rstrip()
        logger.warning(f"Hard truncated intervention text: {len(text)} -> {len(truncated_text)} chars")
        return truncated_text

    def _truncate_intervention_text(self, text: str, max_length: int) -> str:
        """Intelligently truncate intervention text to fit within character limit.
        
        Args:
            text: Original intervention text
            max_length: Maximum allowed character length
            
        Returns:
            Truncated text that fits within the limit
        """
        if len(text) <= max_length:
            return text
        
        # Use AI-powered condensation if enabled, otherwise fall back to simple truncation
        if self.config.get('use_ai_text_condensation', True):
            return self._condense_intervention_text_with_ai(text, max_length)
        else:
            logger.info(f"AI text condensation disabled, using fallback truncation for {len(text)} char text")
            return self._fallback_truncate_intervention_text(text, max_length)

    def _merge_interventions(self, intervention1: Intervention, intervention2: Intervention) -> Intervention:
        """
        Merge two interventions into a single intervention.
        
        Args:
            intervention1: First intervention
            intervention2: Second intervention
            
        Returns:
            A new merged intervention
        """
        logger.info(f"Merging interventions with claims: '{intervention1.claim_text[:30]}...' and '{intervention2.claim_text[:30]}...'")
        
        # Determine the start and end times
        start_time = min(intervention1.timestamp_start, intervention2.timestamp_start)
        end_time = max(intervention1.timestamp_end, intervention2.timestamp_end)
        
        # Combine the claim texts
        combined_claim = f"{intervention1.claim_text} and {intervention2.claim_text}"
        
        # Create a natural transition between the two interventions
        transitions = [
            "Additionally, ", 
            "Furthermore, ", 
            "Also, ", 
            "Moreover, ",
            "What's more, "
        ]
        transition = random.choice(transitions)
        
        # Combine the intervention texts
        if intervention1.intervention_type == intervention2.intervention_type:
            # Both are the same type, create a cohesive narrative
            combined_text = f"{intervention1.intervention_text} {transition}{intervention2.intervention_text.lower()}"
        else:
            # Different types, keep them more separate
            combined_text = f"{intervention1.intervention_text} {transition}{intervention2.intervention_text}"
        
        # Determine the intervention type (correction takes priority)
        combined_type = "correction" if "correction" in (intervention1.intervention_type, intervention2.intervention_type) else "confirmation"
        
        # Apply character limit to the combined text
        max_text_length = self.config.get('max_intervention_text_length', 250)
        final_combined_text = self._truncate_intervention_text(combined_text, max_text_length)
        
        # Create new intervention
        merged_intervention = Intervention(
            timestamp_start=start_time,
            timestamp_end=end_time,
            claim_text=combined_claim,
            intervention_text=final_combined_text,
            intervention_type=combined_type,
            target_duration=None,  # Will need to generate TTS to get actual duration
            audio_file=None,       # Will need to regenerate
            duration=None          # Will need to regenerate
        )
        
        if len(final_combined_text) < len(combined_text):
            logger.info(f"Created merged intervention with truncated text: '{final_combined_text[:50]}...' (was {len(combined_text)} chars, now {len(final_combined_text)} chars)")
        else:
            logger.info(f"Created merged intervention with combined text: '{final_combined_text[:50]}...'")
        return merged_intervention

    def _preprocess_interventions(self, interventions: List[Intervention], video_duration: float) -> List[Intervention]:
        """
        Preprocess interventions to handle constraints like:
        - Merging interventions with short segments between them
        - Adjusting timestamps to respect sentence boundaries
        
        Args:
            interventions: List of interventions to process
            video_duration: Total duration of the video
            
        Returns:
            Processed list of interventions
        """
        if not interventions:
            return []
            
        logger.info(f"Preprocessing {len(interventions)} interventions")
        
        # First, ensure interventions are sorted by timestamp
        interventions.sort(key=lambda x: x.timestamp_start)
        
        # Get configuration parameters
        min_segment_duration = self.config.get('min_segment_duration', 3.0)
        merge_short_segments = self.config.get('merge_short_segments', True)
        enable_sentence_aware_cuts = self.config.get('enable_sentence_aware_cuts', True)
        
        # If we don't need to process any constraints, return original list
        if not merge_short_segments and not enable_sentence_aware_cuts:
            return interventions
        
        # Handle short segments by merging interventions
        if merge_short_segments:
            # Identify short segments between interventions
            short_segment_pairs = []
            
            for i in range(len(interventions) - 1):
                current_end = interventions[i].timestamp_end
                next_start = interventions[i+1].timestamp_start
                segment_duration = next_start - current_end
                
                if segment_duration < min_segment_duration:
                    logger.info(f"Found short segment between intervention {i} and {i+1}: {segment_duration:.2f}s")
                    short_segment_pairs.append((i, i+1))
            
            # If we have short segments, merge the interventions
            if short_segment_pairs:
                # Process merges from the end to avoid index shifting
                short_segment_pairs.sort(reverse=True)
                
                # New list to hold the merged interventions
                merged_interventions = interventions.copy()
                
                for idx1, idx2 in short_segment_pairs:
                    # Get original interventions
                    intervention1 = merged_interventions[idx1]
                    intervention2 = merged_interventions[idx2]
                    
                    # Merge them
                    merged = self._merge_interventions(intervention1, intervention2)
                    
                    # Replace with merged intervention and remove the second one
                    merged_interventions[idx1] = merged
                    merged_interventions.pop(idx2)
                    
                    logger.info(f"Merged interventions at positions {idx1} and {idx2}")
                
                # Update our working list
                interventions = merged_interventions
        
        # Now adjust for sentence boundaries if needed
        if enable_sentence_aware_cuts and self.full_transcript_with_words:
            adjusted_interventions = []
            
            for i, intervention in enumerate(interventions):
                # Determine the start time context
                prev_end = 0.0 if i == 0 else interventions[i-1].timestamp_end
                
                # Find sentence end before intervention start
                lookbehind_seconds = self.config.get('sentence_cut_max_lookbehind', 3.0)
                sentence_end = self._find_closest_sentence_end_before(
                    target_time=intervention.timestamp_start,
                    transcript_with_words=self.full_transcript_with_words,
                    max_lookbehind_seconds=lookbehind_seconds,
                    min_time_from_start=prev_end
                )
                
                # Adjust start time if we found a sentence boundary
                if sentence_end is not None:
                    adjusted_start = sentence_end
                    logger.info(f"Adjusted start time for intervention {i}: {intervention.timestamp_start:.2f}s -> {adjusted_start:.2f}s (sentence boundary)")
                else:
                    adjusted_start = intervention.timestamp_start
                
                # Determine the end time context
                next_start = video_duration if i == len(interventions) - 1 else interventions[i+1].timestamp_start
                
                # Find sentence start after intervention end
                lookahead_seconds = self.config.get('sentence_cut_max_lookahead', 2.0)
                sentence_start = self._find_closest_sentence_start_after(
                    target_time=intervention.timestamp_end,
                    transcript_with_words=self.full_transcript_with_words,
                    max_lookahead_seconds=lookahead_seconds,
                    max_time_to_end=next_start
                )
                
                # Adjust end time if we found a sentence boundary
                if sentence_start is not None:
                    adjusted_end = sentence_start
                    logger.info(f"Adjusted end time for intervention {i}: {intervention.timestamp_end:.2f}s -> {adjusted_end:.2f}s (sentence boundary)")
                else:
                    adjusted_end = intervention.timestamp_end
                
                # Create adjusted intervention
                adjusted_intervention = Intervention(
                    timestamp_start=adjusted_start,
                    timestamp_end=adjusted_end,
                    claim_text=intervention.claim_text,
                    intervention_text=intervention.intervention_text,
                    intervention_type=intervention.intervention_type,
                    target_duration=intervention.target_duration,
                    audio_file=intervention.audio_file,
                    duration=intervention.duration
                )
                
                adjusted_interventions.append(adjusted_intervention)
            
            # Update our working list
            interventions = adjusted_interventions
        
        logger.info(f"Preprocessing complete: {len(interventions)} interventions after merging/adjusting")
        return interventions

    def process_batch(self, batch_file_path: str) -> Dict[str, Any]:
        """Process multiple reels from a batch file.
        
        Args:
            batch_file_path: Path to text file containing URLs (one per line)
            
        Returns:
            Dictionary with batch results and summary
        """
        if not os.path.exists(batch_file_path):
            raise FileNotFoundError(f"Batch file not found: {batch_file_path}")
        
        # Read URLs from file
        urls = []
        with open(batch_file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    urls.append((line_num, line))
        
        if not urls:
            raise ValueError(f"No URLs found in batch file: {batch_file_path}")
        
        logger.info(f"Found {len(urls)} URLs to process from batch file")
        
        # Create batch output directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_output_dir = os.path.join(self.config.get('output_dir', 'output'), f"batch_{timestamp}")
        os.makedirs(batch_output_dir, exist_ok=True)
        
        results = {
            'batch_file': batch_file_path,
            'total_urls': len(urls),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'batch_output_dir': batch_output_dir,
            'results': [],
            'failed_urls': []
        }
        
        logger.info(f"Created batch output directory: {batch_output_dir}")
        
        # Process each URL
        for line_num, url in urls:
            logger.info(f"Processing URL {results['processed'] + 1}/{len(urls)} (line {line_num}): {url}")
            
            try:
                # Create individual output directory for this reel
                url_safe = re.sub(r'[^\w\-_.]', '_', url.split('/')[-1] or f"reel_{line_num}")
                reel_output_dir = os.path.join(batch_output_dir, f"{results['processed'] + 1:03d}_{url_safe}")
                os.makedirs(reel_output_dir, exist_ok=True)
                
                # Temporarily override output directory for this reel
                original_output_dir = self.config.get('output_dir', 'output')
                self.config['output_dir'] = reel_output_dir
                
                # Process the reel
                reel_result = self.process_reel(url)
                
                # Add metadata to result
                reel_result['line_number'] = line_num
                reel_result['url'] = url
                reel_result['reel_output_dir'] = reel_output_dir
                reel_result['status'] = 'success'
                
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
                # Restore original output directory
                self.config['output_dir'] = original_output_dir
                results['processed'] += 1
        
        # Generate batch summary
        self._generate_batch_summary(results)
        
        logger.info(f"Batch processing complete: {results['successful']}/{results['total_urls']} successful")
        return results

    def _generate_batch_summary(self, results: Dict[str, Any]) -> None:
        """Generate a summary report for the batch processing.
        
        Args:
            results: Batch processing results dictionary
        """
        summary_path = os.path.join(results['batch_output_dir'], 'batch_summary.json')
        
        # Create detailed summary
        summary = {
            'batch_info': {
                'batch_file': results['batch_file'],
                'processed_at': datetime.now().isoformat(),
                'total_urls': results['total_urls'],
                'successful': results['successful'],
                'failed': results['failed'],
                'success_rate': f"{(results['successful'] / results['total_urls'] * 100):.1f}%"
            },
            'successful_results': [r for r in results['results'] if r.get('status') == 'success'],
            'failed_results': results['failed_urls']
        }
        
        # Save JSON summary
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        # Create human-readable text summary
        text_summary_path = os.path.join(results['batch_output_dir'], 'batch_summary.txt')
        with open(text_summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("FACTUAL PIPELINE - BATCH PROCESSING SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Batch File: {results['batch_file']}\n")
            f.write(f"Processed At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Output Directory: {results['batch_output_dir']}\n\n")
            
            f.write("STATISTICS:\n")
            f.write(f"  Total URLs: {results['total_urls']}\n")
            f.write(f"  Successful: {results['successful']}\n")
            f.write(f"  Failed: {results['failed']}\n")
            f.write(f"  Success Rate: {(results['successful'] / results['total_urls'] * 100):.1f}%\n\n")
            
            if results['results']:
                f.write("SUCCESSFUL PROCESSING:\n")
                for i, result in enumerate([r for r in results['results'] if r.get('status') == 'success'], 1):
                    f.write(f"  {i:2d}. Line {result['line_number']:2d}: {result['url']}\n")
                    f.write(f"      Output: {result['reel_output_dir']}\n")
                    f.write(f"      Video:  {os.path.basename(result['output_video'])}\n")
                    if result.get('manifest'):
                        f.write(f"      Manifest: {os.path.basename(result['manifest'])}\n")
                    if result.get('summary_slide'):
                        f.write(f"      Summary Slide: {os.path.basename(result['summary_slide'])}\n")
                    f.write("\n")
            
            if results['failed_urls']:
                f.write("FAILED PROCESSING:\n")
                for i, failed in enumerate(results['failed_urls'], 1):
                    f.write(f"  {i:2d}. Line {failed['line_number']:2d}: {failed['url']}\n")
                    f.write(f"      Error: {failed['error']}\n\n")
        
        logger.info(f"Batch summary saved to: {summary_path}")
        logger.info(f"Human-readable summary saved to: {text_summary_path}")

    def _create_slide_minimal_fallback(self, bullet_points: List[str], width: int, height: int,
                                      slide_path: str) -> bool:
        """Minimal fallback using PIL/Pillow if available."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create black image
            img = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(img)
            
            # Try to get a font
            font_size = 42
            try:
                # Try different font paths
                font_paths = [
                    "/System/Library/Fonts/Helvetica.ttc",  # macOS
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux alt
                    "C:\\Windows\\Fonts\\arial.ttf"  # Windows
                ]
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
                if not font:
                    font = ImageFont.load_default()
            except:
                font = ImageFont.load_default()
            
            # Draw title
            title = "FACT-CHECK SUMMARY"
            y_position = int(height * 0.25)
            
            # Get text width for centering
            bbox = draw.textbbox((0, 0), title, font=font)
            text_width = bbox[2] - bbox[0]
            x_position = (width - text_width) // 2
            
            draw.text((x_position, y_position), title, fill='white', font=font)
            
            # Draw bullet points
            y_position = int(height * 0.40)
            line_spacing = 80
            
            for point in bullet_points:
                bullet_text = f"• {point}"
                bbox = draw.textbbox((0, 0), bullet_text, font=font)
                text_width = bbox[2] - bbox[0]
                x_position = (width - text_width) // 2
                
                draw.text((x_position, y_position), bullet_text, fill='white', font=font)
                y_position += line_spacing
            
            # Save image
            img.save(slide_path, 'PNG', quality=95)
            logger.info("Created summary slide using PIL/Pillow")
            return True
            
        except ImportError:
            logger.info("PIL/Pillow not available")
        except Exception as e:
            logger.warning(f"PIL/Pillow method failed: {e}")
        
        # Ultimate fallback - just create black image with FFmpeg
        cmd = [
            self.config['ffmpeg_path'],
            "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d=1",
        ]
        
        # Try to at least add a title with explicit font
        fontfile_path = "/System/Library/Fonts/Helvetica.ttc"
        title_filter = (
            f"drawtext=text='FACT-CHECK SUMMARY':"
            f"fontcolor=white:fontsize=60:"
            f"x=(w-text_w)/2:y=h*0.25:"
            f"fontfile='{fontfile_path}'"
        )
        cmd.extend(["-vf", title_filter])
        
        cmd.extend([
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            slide_path
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.warning("Created slide with title only as fallback")
            return True
        return False

    def _create_intervention_frame_with_pil(self, text: str, width: int, height: int, duration: float, output_path: str, audio_path: str = None, background_image_path: str = None):
        """
        Create intervention frame using PIL for accurate text rendering, then convert to video with FFmpeg.
        This replaces the problematic FFmpeg drawtext approach with precise text measurement and layout.
        """
        logger.info(f"Creating intervention frame with PIL: {output_path}")
        
        # Calculate text area (80% width, 50% height, centered)
        text_width = int(width * 0.80)
        text_height = int(height * 0.50)
        text_x = int(width * 0.10)  # 10% margin from left
        text_y = int(height * 0.25)  # Center vertically (50% height starts at 25%)
        
        # Safety margin to prevent edge clipping
        safe_margin = 0.05  # 5% safety margin
        safe_text_width = int(text_width * (1 - safe_margin))
        safe_text_height = int(text_height * (1 - safe_margin))
        safe_text_x = text_x + int(text_width * safe_margin / 2)
        safe_text_y = text_y + int(text_height * safe_margin / 2)
        
        # Create background image
        if background_image_path and Path(background_image_path).exists():
            try:
                # Load and process background image
                bg_img = Image.open(background_image_path)
                # Resize to match video dimensions
                bg_img = bg_img.resize((width, height), Image.Resampling.LANCZOS)
                # Convert to grayscale
                bg_img = bg_img.convert('L').convert('RGB')
                # Apply dimming effect (make it darker for better text contrast)
                img = Image.new('RGB', (width, height), color='black')
                img.paste(bg_img, (0, 0))
                # Apply semi-transparent black overlay for dimming
                overlay = Image.new('RGBA', (width, height), (0, 0, 0, 102))  # 40% opacity black
                img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
                logger.info(f"Using grayscale background from: {background_image_path}")
            except Exception as e:
                logger.warning(f"Failed to load background image {background_image_path}: {e}, using black background")
                img = Image.new('RGB', (width, height), color='black')
        else:
            # Fallback to black background
            img = Image.new('RGB', (width, height), color='black')
            if background_image_path:
                logger.warning(f"Background image not found: {background_image_path}, using black background")
        
        draw = ImageDraw.Draw(img)
        
        # Try to find a good system font
        font_paths = [
            '/System/Library/Fonts/Helvetica.ttc',
            '/System/Library/Fonts/Arial.ttf', 
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/Windows/Fonts/arial.ttf'
        ]
        
        font_path = None
        for path in font_paths:
            if Path(path).exists():
                font_path = path
                break
        
        # Find optimal font size through iterative testing
        best_font_size = 20
        best_lines = [text]  # fallback
        
        for font_size in range(100, 15, -2):  # Test from large to small
            try:
                if font_path:
                    font = ImageFont.truetype(font_path, font_size)
                else:
                    font = ImageFont.load_default()
                
                # Word wrap to fit width
                words = text.split()
                lines = []
                current_line = ""
                
                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    line_width = bbox[2] - bbox[0]
                    
                    if line_width <= safe_text_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                
                if current_line:
                    lines.append(current_line)
                
                # Check if total height fits
                if lines:
                    sample_bbox = draw.textbbox((0, 0), lines[0], font=font)
                    line_height = sample_bbox[3] - sample_bbox[1]
                    total_height = len(lines) * line_height * 1.2  # 20% line spacing
                    
                    if total_height <= safe_text_height:
                        best_font_size = font_size
                        best_lines = lines
                        break
                        
            except Exception as e:
                logger.warning(f"Font size {font_size} failed: {e}")
                continue
        
        # Render the final text
        try:
            if font_path:
                final_font = ImageFont.truetype(font_path, best_font_size)
            else:
                final_font = ImageFont.load_default()
            
            # Calculate line height
            sample_bbox = draw.textbbox((0, 0), "Ay", font=final_font)
            line_height = int((sample_bbox[3] - sample_bbox[1]) * 1.2)
            
            # Center text block vertically within safe area
            total_text_height = len(best_lines) * line_height
            start_y = safe_text_y + (safe_text_height - total_text_height) // 2
            
            # Draw each line
            for i, line in enumerate(best_lines):
                line_y = start_y + (i * line_height)
                
                # Center line horizontally within safe area
                bbox = draw.textbbox((0, 0), line, font=final_font)
                line_width = bbox[2] - bbox[0]
                line_x = safe_text_x + (safe_text_width - line_width) // 2
                
                # Draw text with outline for better visibility
                outline_width = 2
                for dx in range(-outline_width, outline_width + 1):
                    for dy in range(-outline_width, outline_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((line_x + dx, line_y + dy), line, font=final_font, fill='black')
                
                # Draw main text
                draw.text((line_x, line_y), line, font=final_font, fill='white')
            
            logger.info(f"Rendered text with {len(best_lines)} lines, font size {best_font_size}")
            
        except Exception as e:
            logger.error(f"Text rendering failed: {e}")
            # Fallback: simple centered text
            draw.text((width//2, height//2), "Text rendering error", anchor="mm", fill='white')
        
        # Save as temporary PNG
        temp_png_path = output_path.replace('.mp4', '_temp.png')
        img.save(temp_png_path, 'PNG')
        
        # Convert PNG to video with audio using FFmpeg
        try:
            if audio_path and Path(audio_path).exists():
                # Create video from image with TTS audio
                ffmpeg_cmd = [
                    self.config['ffmpeg_path'], '-y',
                    '-loop', '1', '-i', temp_png_path,
                    '-i', audio_path,
                    '-c:v', 'libx264', '-c:a', 'aac',
                    '-shortest', '-pix_fmt', 'yuv420p',
                    output_path
                ]
            else:
                # Create video from image with duration (silent)
                ffmpeg_cmd = [
                    self.config['ffmpeg_path'], '-y',
                    '-loop', '1', '-i', temp_png_path,
                    '-c:v', 'libx264', '-t', str(duration),
                    '-pix_fmt', 'yuv420p',
                    output_path
                ]
            
            logger.info(f"Creating video from PIL image: {' '.join(ffmpeg_cmd)}")
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Successfully created intervention video: {output_path}")
            else:
                logger.error(f"FFmpeg failed: {result.stderr}")
                raise Exception(f"FFmpeg conversion failed: {result.stderr}")
                
        finally:
            # Clean up temporary PNG
            if Path(temp_png_path).exists():
                Path(temp_png_path).unlink()
        
        return output_path

    def _prepare_text_overlay(self, text: str, width: int, height: int):
        """Prepare a drawtext filter string that fits text inside 80% width and 50% height.
        Returns (drawtext_filter:str, temp_text_file:str|None, fontsize:int)
        Caller is responsible for deleting the temp file when done.
        """
        import tempfile, os
        # Use centralized text box calculation for consistent positioning
        ffmpeg_helper = FFmpegHelper(self.config['ffmpeg_path'])
        text_params = ffmpeg_helper.calculate_text_box_params(width, height)
        target_text_height_ratio = 0.50
        font_size_clamp = (20, 100)
        line_height_factor = 1.25
        avg_char_width_factor = 0.45  # heuristic

        # ULTRA-CONSERVATIVE APPROACH: Use much larger safety margins and simple wrapping
        # Apply 15% safety margin to prevent any possibility of edge cutoffs
        raw_target_w_px = text_params['text_width_px']  # Exact 80% width in pixels
        target_w_px = int(raw_target_w_px * 0.85)  # 15% safety margin for width
        x_offset_px = text_params['text_x_offset_px']  # Exact 10% offset in pixels
        safe_area_h = height * target_text_height_ratio * 0.85  # 15% safety margin for height
        
        # Use very conservative character limit based on smallest expected character
        # At font size 30, average character is about 15px wide
        # Use even more conservative estimate
        conservative_chars_per_line = max(15, int(target_w_px / 20))  # Assume 20px per char (very conservative)
        
        def wrap_conservative(words, max_chars):
            lines = []
            current_line = ""
            for word in words:
                if not current_line:
                    current_line = word
                elif len(current_line) + 1 + len(word) <= max_chars:
                    current_line += " " + word
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            return lines
        
        words = text.split()
        
        # Wrap text with conservative character limit
        lines_final = wrap_conservative(words, conservative_chars_per_line)
        
        # Calculate font size to fit the wrapped text in available height
        num_lines = len(lines_final)
        calculated_fontsize = int(safe_area_h / (num_lines * line_height_factor))
        best_fontsize = max(font_size_clamp[0], min(calculated_fontsize, font_size_clamp[1]))
        
        fontsize = best_fontsize
        formatted="\n".join(lines_final)
        
        temp_path=None
        try:
            tmp=tempfile.NamedTemporaryFile(mode="w+",delete=False,suffix=".txt",encoding="utf-8")
            tmp.write(formatted)
            tmp.close()
            temp_path=tmp.name
            safe_path=temp_path.replace("\\","/")
            # CRITICAL FIX: Use expansion=none to prevent FFmpeg from interpreting % symbols as format specifiers
            # This ensures text with percentages (like "80%") renders correctly
            # ELEGANT SOLUTION: Use safety-margin width for BOTH text wrapping AND FFmpeg boxw to ensure consistency
            draw=f"drawtext=textfile='{safe_path}':fontcolor=white:fontsize={fontsize}:x={x_offset_px}:y=(h-text_h)/2:boxw={target_w_px}:line_spacing=20:borderw=2:bordercolor=black@0.5:box=1:boxcolor=black@0.5:boxborderw=10:expansion=none"
        except Exception:
            # fallback to literal space with consistent positioning and width constraint (using safety margin)
            draw=f"drawtext=text=' ':fontcolor=white:fontsize={fontsize}:x={x_offset_px}:y=(h-text_h)/2:boxw={target_w_px}:expansion=none"
        return draw,temp_path,fontsize

    def _write_sources_file(self, interventions: List[Intervention], output_dir: str) -> str:
        """Write a human-readable sources.txt file listing detailed sources for each claim.

        Format:
        Claim: "<claim text>"
        Response: <brief summary of intervention>
        Source: <detailed description with study details>
        Link: <url>
        """
        if not interventions:
            return ""

        try:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            sources_path = output_dir_path / "sources.txt"

            with open(sources_path, "w", encoding="utf-8") as f:
                f.write("FACTUAL SOURCES\n")
                f.write("===============\n\n")
                f.write("Detailed sources for factual claims identified in this video.\n")
                f.write("Use this information in video descriptions to provide credible backing for fact-checks.\n\n")

                for i, intervention in enumerate(interventions, 1):
                    claim_text = intervention.claim_text.strip().replace("\n", " ")
                    f.write(f"{i}. CLAIM: \"{claim_text}\"\n")
                    
                    # Brief summary of the response (first 100 chars)
                    response_summary = intervention.intervention_text[:100] + "..." if len(intervention.intervention_text) > 100 else intervention.intervention_text
                    f.write(f"   RESPONSE: {response_summary}\n")
                    
                    if intervention.sources:
                        for j, source in enumerate(intervention.sources, 1):
                            title = source.get("title", "No title provided")
                            description = source.get("description", "No description provided")
                            url = source.get("url", "No URL provided")
                            
                            f.write(f"   SOURCE {j}: {title}\n")
                            f.write(f"   DETAILS: {description}\n")
                            f.write(f"   LINK: {url}\n")
                            f.write("\n")
                    else:
                        f.write("   SOURCE: No sources provided by AI model\n")
                        f.write("\n")

            logger.info(f"Written sources list: {sources_path}")
            return str(sources_path)
        except Exception as e:
            logger.warning(f"Failed to write sources.txt: {e}")
            return ""


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Process social media videos (Instagram/Facebook) for fact-checking")
    
    # Create mutually exclusive group for single URL vs batch processing
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("url", nargs='?', help="URL of the Instagram or Facebook video to process")
    url_group.add_argument("--batch", help="Path to text file containing URLs (one per line) for batch processing")
    
    parser.add_argument("--config", help="Path to configuration file")
    
    # Add debugging options
    parser.add_argument("--debug-visual", action="store_true", help="Enable visual checkpoint verification (frames)")
    parser.add_argument("--debug-segments", action="store_true", help="Enable saving individual segments")
    parser.add_argument("--debug-manifest", action="store_true", help="Enable detailed sequence manifest")
    parser.add_argument("--debug-all", action="store_true", help="Enable all debugging options")
    parser.add_argument("--use-sample", action="store_true", help="Use a sample video instead of downloading from Instagram")
    parser.add_argument("--no-text", action="store_true", help="Don't render intervention text, only show watermarks")
    parser.add_argument("--no-summary", action="store_true", help="Don't include summary frame at the end")
    parser.add_argument("--no-slide", action="store_true", help="Don't generate summary slide PNG for manual addition")
    parser.add_argument("--test-url", action="store_true", 
                       help="Use the verified test URL that works with this pipeline (Instagram: https://www.instagram.com/reel/DE_C78HyOVM/ or Facebook: https://www.facebook.com/watch?v=XXXX)")
    
    args = parser.parse_args()
    
    try:
        pipeline = FactualPipeline(args.config)
        
        # Set debugging options if specified
        if args.debug_all:
            pipeline.config['debug_visual_checkpoints'] = True
            pipeline.config['debug_save_segments'] = True
            pipeline.config['debug_sequence_manifest'] = True
            logger.info("All debugging options enabled")
        else:
            if args.debug_visual:
                pipeline.config['debug_visual_checkpoints'] = True
                logger.info("Visual checkpoint verification enabled")
            if args.debug_segments:
                pipeline.config['debug_save_segments'] = True
                logger.info("Segment-by-segment testing enabled")
            if args.debug_manifest:
                pipeline.config['debug_sequence_manifest'] = True
                logger.info("JSON sequence manifest enabled")
        
        # Enable sample video mode if specified
        if args.use_sample:
            pipeline.config['use_sample_video'] = True
            logger.info("Using sample video mode - will not download from Instagram")
            
        # Disable text rendering if specified
        if args.no_text:
            pipeline.config['render_intervention_text'] = False
            logger.info("Text rendering disabled - only watermarks will be shown")
            
        # Disable summary frame if specified
        if args.no_summary:
            pipeline.config['include_summary_frame'] = False
            logger.info("Summary frame disabled - will not include factual claims summary")
        
        # Disable summary slide if specified
        if args.no_slide:
            pipeline.config['generate_summary_slide'] = False
            logger.info("Summary slide generation disabled - will not create PNG slide for manual addition")
        
        # Handle batch processing mode
        if args.batch:
            logger.info(f"Starting batch processing from file: {args.batch}")
            print(f"\nStarting batch processing from file: {args.batch}")
            
            try:
                batch_results = pipeline.process_batch(args.batch)
            except ValueError as e:
                if "ElevenLabs API key is" in str(e):
                    logger.error(f"ElevenLabs API key validation failed: {str(e)}")
                    logger.info("Will proceed with silent audio for interventions in batch mode")
                    batch_results = pipeline.process_batch(args.batch)
                else:
                    raise
            
            # Print batch results summary
            print(f"\nBatch processing complete!")
            print(f"Total URLs: {batch_results['total_urls']}")
            print(f"Successful: {batch_results['successful']}")
            print(f"Failed: {batch_results['failed']}")
            print(f"Success Rate: {(batch_results['successful'] / batch_results['total_urls'] * 100):.1f}%")
            print(f"Batch output directory: {batch_results['batch_output_dir']}")
            print(f"Summary files:")
            print(f"  - JSON: {os.path.join(batch_results['batch_output_dir'], 'batch_summary.json')}")
            print(f"  - Text: {os.path.join(batch_results['batch_output_dir'], 'batch_summary.txt')}")
            
            if batch_results['failed'] > 0:
                print(f"\nFailed URLs:")
                for failed in batch_results['failed_urls']:
                    print(f"  Line {failed['line_number']}: {failed['url']} - {failed['error']}")
            
            return
        
        # Handle single URL processing (original mode)
        url = args.url
        if args.test_url:
            url = "https://www.instagram.com/reel/DE_C78HyOVM/?igsh=MWh5dTU4NzltM296Zw=="
            logger.info(f"Using verified test URL that works with this pipeline: {url}")
        
        # Track if we're using silent audio fallback
        using_silent_audio = False
        
        try:
            result = pipeline.process_reel(url)
        except ValueError as e:
            if "ElevenLabs API key is" in str(e):
                logger.error(f"ElevenLabs API key validation failed: {str(e)}")
                logger.info("Will proceed with silent audio for interventions")
                using_silent_audio = True
                result = pipeline.process_reel(url)
            else:
                raise
        
        print("\nProcessing complete!")
        print(f"Input video: {result['input_video']}")
        print(f"Output video: {result['output_video']}")
        print(f"Manifest: {result['manifest']}")
        if result['preview']:
            print(f"Preview: {result['preview']}")
        if result.get('summary_slide'):
            print(f"Summary slide: {result['summary_slide']}")
            print("💡 Use this PNG slide to manually add a summary to your reel before uploading!")
        
        # Print API key warning if applicable
        if using_silent_audio:
            print("\n" + "!" * 80)
            print("WARNING: ElevenLabs API key validation failed. Silent audio was used for interventions.")
            print("To fix this issue:")
            print("1. Check your ElevenLabs API key at https://elevenlabs.io/app/account")
            print("2. Update your config.json file with the valid API key")
            print("3. Or set the ELEVENLABS_API_KEY environment variable")
            print("!" * 80)
        
        # Print debugging information if enabled
        output_dir = os.path.dirname(result['output_video'])
        if pipeline.config.get('debug_visual_checkpoints', False):
            debug_frames_dir = os.path.join(output_dir, "debug_frames")
            if os.path.exists(debug_frames_dir):
                print(f"\nVisual checkpoint frames: {debug_frames_dir}")
                print("View these frames to verify the correct visual sequence")
        
        if pipeline.config.get('debug_save_segments', False):
            debug_segments_dir = os.path.join(output_dir, "debug_segments")
            if os.path.exists(debug_segments_dir):
                print(f"\nIndividual segments: {debug_segments_dir}")
                print("Play these segments individually to verify correct content and audio")
                
                # Count and list segments by type for easier debugging
                try:
                    original_segments = [f for f in os.listdir(debug_segments_dir) if f.startswith("original_")]
                    intervention_segments = [f for f in os.listdir(debug_segments_dir) if f.startswith("intervention_")]
                    
                    print(f"  - Original segments saved: {len(original_segments)}")
                    print(f"  - Intervention segments saved: {len(intervention_segments)}")
                    
                    # Ask if user wants to open the directory
                    if sys.platform == 'darwin':  # macOS
                        try:
                            open_dir = input("\nWould you like to open the debug segments directory now? (y/n): ")
                            if open_dir.lower() == 'y':
                                subprocess.run(['open', debug_segments_dir])
                                print(f"Opened {debug_segments_dir}")
                        except Exception as e:
                            print(f"Could not open directory: {str(e)}")
                    elif sys.platform == 'win32':  # Windows
                        try:
                            open_dir = input("\nWould you like to open the debug segments directory now? (y/n): ")
                            if open_dir.lower() == 'y':
                                os.startfile(debug_segments_dir)
                                print(f"Opened {debug_segments_dir}")
                        except Exception as e:
                            print(f"Could not open directory: {str(e)}")
                    elif sys.platform.startswith('linux'):  # Linux
                        try:
                            open_dir = input("\nWould you like to open the debug segments directory now? (y/n): ")
                            if open_dir.lower() == 'y':
                                subprocess.run(['xdg-open', debug_segments_dir])
                                print(f"Opened {debug_segments_dir}")
                        except Exception as e:
                            print(f"Could not open directory: {str(e)}")
                except Exception as e:
                    print(f"Error listing debug segments: {str(e)}")
        
        if pipeline.config.get('debug_sequence_manifest', False):
            sequence_manifest = os.path.join(output_dir, "sequence_manifest.json")
            if os.path.exists(sequence_manifest):
                print(f"\nSequence manifest: {sequence_manifest}")
                print("Check this JSON file to see the exact segment order and details")
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 