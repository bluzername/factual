# Factual - Instagram Reels Fact-Checking Pipeline

An automated system for fact-checking Instagram Reels, providing corrective factual commentary, and generating a composite video with factual interventions.

## Overview

This pipeline performs the following steps:
1. Downloads an Instagram Reel given a URL
2. Transcribes the audio using OpenAI Whisper
3. Identifies factual claims and generates corrective commentary using GPT-4o
4. Creates TTS narration for the commentary using ElevenLabs
5. Edits the video to include pauses, black frames with commentary, and branding
6. Outputs a final composite video with factual interventions

## Requirements

- Python 3.8+
- FFmpeg (installed and in PATH)
- yt-dlp (installed and in PATH)
- ImageMagick (optional, for preview generation)
- OpenAI API key
- ElevenLabs API key

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/factual.git
cd factual
```

2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

3. Create necessary directories:
```bash
mkdir -p assets output temp
```

4. Add your logo watermark to the assets directory:
```bash
# Add your logo watermark at assets/logo_watermark.png
# Recommended size: 200x200px with transparency
```

5. Update the configuration file with your API keys:
```bash
# Edit config.json with your API keys
```

## Usage

### Basic Usage

Process an Instagram Reel with default settings:

```bash
python factual_pipeline.py https://www.instagram.com/reel/XYZABCDEFG/
```

### Using a Configuration File

```bash
python factual_pipeline.py https://www.instagram.com/reel/XYZABCDEFG/ --config my_config.json
```

### Environment Variables

You can also set your API keys as environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ELEVENLABS_API_KEY="your-elevenlabs-api-key"
python factual_pipeline.py https://www.instagram.com/reel/XYZABCDEFG/
```

## Output

The pipeline generates several outputs:

- **Composite Video**: The final fact-checked video with interventions
- **JSON Manifest**: A file containing details about the processed video and interventions
- **Visual Preview**: A grid of thumbnails showing where interventions were inserted (requires ImageMagick)

All outputs are saved to the `output/{session_id}/` directory.

## FFmpeg Commands

The pipeline uses several FFmpeg commands:

1. **Extract Audio for Transcription**:
```bash
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 -y output.wav
```

2. **Extract Video Segment**:
```bash
ffmpeg -ss START_TIME -i input.mp4 -t DURATION -c copy -y segment.mp4
```

3. **Create Black Frame with Text and Audio**:
```bash
ffmpeg -f lavfi -i "color=c=black:s=WIDTHxHEIGHT:d=DURATION" -i audio.mp3 -vf "drawtext=text='TEXT':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2" -c:v libx264 -c:a aac -shortest -y output.mp4
```

4. **Concatenate Video Segments**:
```bash
ffmpeg -f concat -safe 0 -i concat.txt -c copy -y output.mp4
```

5. **Add Watermark**:
```bash
ffmpeg -i input.mp4 -i watermark.png -filter_complex "[0:v][1:v]overlay=10:10" -c:a copy -y output.mp4
```

## Example JSON Manifest

```json
{
  "original_video": "temp/20230615123456/reel.mp4",
  "final_video": "output/20230615123456/factual_output.mp4",
  "interventions": [
    {
      "timestamp_start": 3.2,
      "timestamp_end": 5.8,
      "claim_text": "The Earth is flat.",
      "intervention_text": "The Earth is not flat but an oblate spheroid. This has been confirmed by satellite imagery, physics calculations, and direct observation.",
      "intervention_type": "correction",
      "audio_file": "temp/20230615123456/tts/intervention_0.mp3",
      "duration": 6.5
    }
  ],
  "total_video_duration": 45.3,
  "processed_at": "2023-06-15T12:34:56.789012"
}
```

## Limitations

- The system relies on GPT-4o's general knowledge and does not perform web searches for fact verification
- The accuracy of transcription depends on audio quality and clarity of speech
- Instagram occasionally changes their platform, which may affect the download functionality

## Future Enhancements

- Web search integration for real-time fact verification
- Customizable graphic templates for fact-checking overlays
- Support for additional social media platforms
- Fine-tuned models for specific domains (e.g., health, science, politics)

## License

[MIT License](LICENSE) 