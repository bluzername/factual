"""Model identifiers for the Factual pipeline, in one place.

Every id can be overridden with an environment variable. The defaults are
the ids the pipeline shipped with, except the TTS model, which was moved
from the deprecated eleven_turbo_v2 to its documented replacement.
"""

import os

DEFAULT_LLM_MODEL = os.environ.get("FACTUAL_LLM_MODEL", "gpt-5-nano")
DEFAULT_LLM_MINI_MODEL = os.environ.get("FACTUAL_LLM_MINI_MODEL", "gpt-5-nano")
DEFAULT_WHISPER_MODEL = os.environ.get("FACTUAL_WHISPER_MODEL", "whisper-1")
DEFAULT_TTS_MODEL = os.environ.get("FACTUAL_TTS_MODEL", "eleven_flash_v2")
DEFAULT_TTS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

__all__ = [
    "DEFAULT_LLM_MODEL",
    "DEFAULT_LLM_MINI_MODEL",
    "DEFAULT_WHISPER_MODEL",
    "DEFAULT_TTS_MODEL",
    "DEFAULT_TTS_VOICE_ID",
]
