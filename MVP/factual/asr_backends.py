#!/usr/bin/env python3
"""
ASR Backend System for Factual Pipeline

Supports multiple transcription backends:
- NVIDIA Parakeet TDT 0.6B v2 (local, high quality)
- faster-whisper (local, lightweight)
- OpenAI Whisper API (cloud, fallback)

The Parakeet backend provides superior accuracy with timestamps and is the default.
"""

import os
import json
import logging
import tempfile
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
# Optional imports - handled within backends
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

try:
    import torchaudio
    TORCHAUDIO_AVAILABLE = True
except ImportError:
    torchaudio = None
    TORCHAUDIO_AVAILABLE = False

logger = logging.getLogger(__name__)


class ASRBackend(ABC):
    """Abstract base class for ASR backends"""
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribe audio file to segments with timestamps
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            List of segments with format:
            [
                {
                    'start': float,  # seconds
                    'end': float,    # seconds  
                    'text': str,     # transcribed text
                    'words': [       # optional word-level timestamps
                        {'start': float, 'end': float, 'text': str},
                        ...
                    ]
                },
                ...
            ]
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available and properly configured"""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get backend information"""
        pass


class ParakeetASRBackend(ASRBackend):
    """NVIDIA Parakeet TDT 0.6B v2 ASR backend"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.model_name = "nvidia/parakeet-tdt-0.6b-v2"
        
        # Configuration options
        self.device = config.get('parakeet_device', 'auto')
        self.batch_size = config.get('parakeet_batch_size', 1)
        self.enable_timestamps = config.get('parakeet_timestamps', True)
        
        # Auto-detect device if needed
        if self.device == 'auto':
            if TORCH_AVAILABLE and torch.cuda.is_available():
                self.device = 'cuda'
                logger.info("CUDA detected, using GPU for Parakeet")
            else:
                self.device = 'cpu'
                logger.info("CUDA not available, using CPU for Parakeet")
    
    def is_available(self) -> bool:
        """Check if Parakeet backend is available"""
        try:
            import nemo.collections.asr as nemo_asr
            return True
        except ImportError:
            logger.warning("NeMo not installed. Install with: pip install nemo_toolkit[asr]")
            return False
    
    def _load_model(self):
        """Lazy load the Parakeet model"""
        if self.model is not None:
            return
        
        try:
            import nemo.collections.asr as nemo_asr
            
            logger.info(f"Loading Parakeet model: {self.model_name}")
            self.model = nemo_asr.models.ASRModel.from_pretrained(model_name=self.model_name)
            
            # Move to specified device
            if self.device == 'cuda' and TORCH_AVAILABLE and torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("Parakeet model loaded on GPU")
            else:
                self.model = self.model.cpu()
                logger.info("Parakeet model loaded on CPU")
                
        except Exception as e:
            logger.error(f"Failed to load Parakeet model: {str(e)}")
            raise RuntimeError(f"Parakeet model loading failed: {str(e)}")
    
    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribe using Parakeet with timestamps"""
        self._load_model()
        
        try:
            # Ensure we have a valid audio file
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Convert to format Parakeet expects if needed
            processed_audio = self._preprocess_audio(audio_path)
            
            logger.info(f"Transcribing with Parakeet: {processed_audio}")
            
            # Transcribe with timestamps
            if self.enable_timestamps:
                output = self.model.transcribe([processed_audio], timestamps=True)
                segments = self._parse_parakeet_output_with_timestamps(output[0])
            else:
                output = self.model.transcribe([processed_audio])
                segments = self._parse_parakeet_output_simple(output[0])
            
            logger.info(f"Parakeet transcription complete: {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Parakeet transcription failed: {str(e)}")
            raise RuntimeError(f"Parakeet transcription error: {str(e)}")
        finally:
            # Clean up temporary files
            if 'processed_audio' in locals() and processed_audio != audio_path and os.path.exists(processed_audio):
                try:
                    os.unlink(processed_audio)
                except:
                    pass
    
    def _preprocess_audio(self, audio_path: str) -> str:
        """Preprocess audio to format expected by Parakeet (16kHz mono WAV)"""
        
        # Check if already in correct format
        try:
            import soundfile as sf
            data, sample_rate = sf.read(audio_path)
            
            # Check if already 16kHz mono
            if sample_rate == 16000 and (data.ndim == 1 or data.shape[1] == 1):
                return audio_path
                
        except ImportError:
            # Fall back to torchaudio
            pass
        except Exception as e:
            logger.warning(f"Could not check audio format: {e}")
        
        # Convert using ffmpeg
        try:
            temp_audio = tempfile.mktemp(suffix='.wav')
            
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',      # mono
                '-y',            # overwrite
                temp_audio
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.debug("Audio converted to 16kHz mono WAV for Parakeet")
            return temp_audio
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Audio conversion failed: {e.stderr}")
            raise RuntimeError(f"Audio preprocessing failed: {e.stderr}")
        except FileNotFoundError:
            logger.error("ffmpeg not found. Please install ffmpeg.")
            raise RuntimeError("ffmpeg required for audio preprocessing")
    
    def _parse_parakeet_output_with_timestamps(self, output) -> List[Dict[str, Any]]:
        """Parse Parakeet output with timestamp information"""
        
        segments = []
        
        try:
            # Get segment-level timestamps
            segment_timestamps = output.timestamp.get('segment', [])
            
            for segment_info in segment_timestamps:
                segment = {
                    'start': float(segment_info['start']),
                    'end': float(segment_info['end']),
                    'text': segment_info['segment'].strip()
                }
                
                # Add word-level timestamps if available
                word_timestamps = output.timestamp.get('word', [])
                segment_words = []
                
                for word_info in word_timestamps:
                    # Check if word belongs to this segment
                    if (segment['start'] <= word_info['start'] <= segment['end']):
                        segment_words.append({
                            'start': float(word_info['start']),
                            'end': float(word_info['end']),
                            'text': word_info['word']
                        })
                
                if segment_words:
                    segment['words'] = segment_words
                
                segments.append(segment)
                
        except Exception as e:
            logger.warning(f"Error parsing Parakeet timestamps: {e}")
            # Fall back to simple parsing
            return self._parse_parakeet_output_simple(output)
        
        return segments
    
    def _parse_parakeet_output_simple(self, output) -> List[Dict[str, Any]]:
        """Parse Parakeet output without timestamps"""
        
        # Simple case: single segment with full text
        text = output.text if hasattr(output, 'text') else str(output)
        
        return [{
            'start': 0.0,
            'end': 0.0,  # Unknown duration
            'text': text.strip()
        }]
    
    def get_info(self) -> Dict[str, Any]:
        """Get Parakeet backend information"""
        return {
            'name': 'Parakeet TDT 0.6B v2',
            'model': self.model_name,
            'device': self.device,
            'timestamps': self.enable_timestamps,
            'available': self.is_available(),
            'description': 'NVIDIA Parakeet TDT 0.6B v2 - High accuracy local ASR with timestamps'
        }


class FasterWhisperBackend(ASRBackend):
    """faster-whisper local ASR backend"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.model_size = config.get('local_whisper_model', 'small')
        self.compute_type = config.get('local_whisper_compute', 'int8')
        self.device = config.get('whisper_device', 'auto')
    
    def is_available(self) -> bool:
        """Check if faster-whisper is available"""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False
    
    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribe using faster-whisper"""
        if not self.is_available():
            raise RuntimeError("faster-whisper not available")
        
        from faster_whisper import WhisperModel
        
        if self.model is None:
            logger.info(f"Loading faster-whisper model: {self.model_size}")
            self.model = WhisperModel(self.model_size, compute_type=self.compute_type)
        
        logger.info(f"Transcribing with faster-whisper ({self.model_size}, {self.compute_type})")
        
        segments = []
        result, info = self.model.transcribe(
            str(audio_path), 
            beam_size=1, 
            vad_filter=True, 
            word_timestamps=True
        )
        
        for seg in result:
            segment = {
                'start': seg.start,
                'end': seg.end,
                'text': seg.text
            }
            
            # Add word-level timestamps if available
            if hasattr(seg, 'words') and seg.words:
                segment['words'] = [
                    {
                        'start': word.start,
                        'end': word.end,
                        'text': word.word
                    }
                    for word in seg.words
                ]
            
            segments.append(segment)
        
        return segments
    
    def get_info(self) -> Dict[str, Any]:
        """Get faster-whisper backend information"""
        return {
            'name': 'faster-whisper',
            'model': self.model_size,
            'compute_type': self.compute_type,
            'device': self.device,
            'available': self.is_available(),
            'description': 'Local Whisper implementation using faster-whisper'
        }


class OpenAIWhisperBackend(ASRBackend):
    """OpenAI Whisper API backend"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get('openai_api_key', '')
        self.model = config.get('whisper_model', 'whisper-1')
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        if not self.api_key:
            return False
        
        try:
            from openai import OpenAI
            return True
        except ImportError:
            return False
    
    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribe using OpenAI Whisper API"""
        if not self.is_available():
            raise RuntimeError("OpenAI Whisper API not available")
        
        from openai import OpenAI
        
        client = OpenAI(api_key=self.api_key)
        
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                response_format="verbose_json"
            )
        
        segments = []
        if hasattr(transcription, 'segments') and transcription.segments:
            for seg in transcription.segments:
                segments.append({
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text']
                })
        else:
            # Fallback: single segment
            segments.append({
                'start': 0.0,
                'end': 0.0,
                'text': transcription.text
            })
        
        return segments
    
    def get_info(self) -> Dict[str, Any]:
        """Get OpenAI Whisper backend information"""
        return {
            'name': 'OpenAI Whisper API',
            'model': self.model,
            'available': self.is_available(),
            'description': 'OpenAI Whisper API - Cloud-based transcription'
        }


class ASRManager:
    """Manages ASR backends and provides unified interface"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backends = {}
        self._initialize_backends()
    
    def _initialize_backends(self):
        """Initialize all available backends"""
        
        # Initialize Parakeet backend (preferred)
        self.backends['parakeet'] = ParakeetASRBackend(self.config)
        
        # Initialize faster-whisper backend
        self.backends['faster_whisper'] = FasterWhisperBackend(self.config)
        
        # Initialize OpenAI backend
        self.backends['openai'] = OpenAIWhisperBackend(self.config)
    
    def get_available_backends(self) -> List[str]:
        """Get list of available backend names"""
        return [name for name, backend in self.backends.items() if backend.is_available()]
    
    def get_backend_info(self, backend_name: str = None) -> Dict[str, Any]:
        """Get information about backends"""
        if backend_name:
            if backend_name in self.backends:
                return self.backends[backend_name].get_info()
            else:
                raise ValueError(f"Unknown backend: {backend_name}")
        else:
            # Return info for all backends
            return {name: backend.get_info() for name, backend in self.backends.items()}
    
    def transcribe(self, audio_path: str, backend: str = 'auto') -> List[Dict[str, Any]]:
        """
        Transcribe audio using specified backend
        
        Args:
            audio_path: Path to audio file
            backend: Backend to use ('auto', 'parakeet', 'faster_whisper', 'openai')
            
        Returns:
            List of transcript segments with timestamps
        """
        
        # Determine backend to use
        if backend == 'auto':
            backend = self._select_best_backend()
        
        if backend not in self.backends:
            raise ValueError(f"Unknown backend: {backend}")
        
        backend_obj = self.backends[backend]
        
        if not backend_obj.is_available():
            # Try fallback
            logger.warning(f"Backend {backend} not available, trying fallback")
            backend = self._select_fallback_backend(exclude=[backend])
            if not backend:
                raise RuntimeError("No ASR backends available")
            backend_obj = self.backends[backend]
        
        logger.info(f"Using ASR backend: {backend}")
        
        try:
            return backend_obj.transcribe(audio_path)
        except Exception as e:
            logger.error(f"Transcription failed with {backend}: {str(e)}")
            
            # Try fallback backend
            fallback = self._select_fallback_backend(exclude=[backend])
            if fallback:
                logger.info(f"Trying fallback backend: {fallback}")
                return self.backends[fallback].transcribe(audio_path)
            else:
                raise RuntimeError(f"All ASR backends failed. Last error: {str(e)}")
    
    def _select_best_backend(self) -> str:
        """Select the best available backend"""
        
        # Preference order: Parakeet > faster-whisper > OpenAI
        preferences = ['parakeet', 'faster_whisper', 'openai']
        
        for backend_name in preferences:
            if backend_name in self.backends and self.backends[backend_name].is_available():
                return backend_name
        
        raise RuntimeError("No ASR backends available")
    
    def _select_fallback_backend(self, exclude: List[str] = None) -> Optional[str]:
        """Select a fallback backend"""
        exclude = exclude or []
        
        preferences = ['parakeet', 'faster_whisper', 'openai']
        
        for backend_name in preferences:
            if (backend_name not in exclude and 
                backend_name in self.backends and 
                self.backends[backend_name].is_available()):
                return backend_name
        
        return None
