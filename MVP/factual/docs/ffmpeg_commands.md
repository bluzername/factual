# FFmpeg Commands Reference

This document provides the FFmpeg commands used in the Factual pipeline with explanations.

## 1. Extract Audio for Transcription

Extracts audio from the video for Whisper transcription, converting to 16kHz mono WAV:

```bash
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 -y output.wav
```

Parameters:
- `-i input.mp4`: Input video file
- `-vn`: No video output (audio only)
- `-acodec pcm_s16le`: Convert to PCM 16-bit little-endian format
- `-ar 16000`: Set sample rate to 16kHz (optimal for Whisper)
- `-ac 1`: Convert to mono audio
- `-y`: Overwrite output file if it exists

## 2. Extract Video Segment

Extracts a segment from the video starting at a specific timestamp:

```bash
ffmpeg -ss 10.5 -i input.mp4 -t 5.0 -c copy -y segment.mp4
```

Parameters:
- `-ss 10.5`: Start timestamp in seconds
- `-i input.mp4`: Input video file
- `-t 5.0`: Duration in seconds
- `-c copy`: Copy codec (no re-encoding to preserve quality)
- `-y`: Overwrite output file if it exists

## 3. Create Black Frame with Text and Audio

Creates a black frame video with text overlay and audio:

```bash
ffmpeg -f lavfi -i "color=c=black:s=1080x1920:d=6.5" -i audio.mp3 -vf "drawtext=text='This is a factual correction':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2" -c:v libx264 -c:a aac -shortest -y output.mp4
```

Parameters:
- `-f lavfi`: Use Libavfilter input
- `-i "color=c=black:s=1080x1920:d=6.5"`: Create black screen with specified dimensions and duration
- `-i audio.mp3`: Audio file to add to the video
- `-vf "drawtext=..."`: Add text overlay with specified parameters
- `-c:v libx264`: Use H.264 codec for video
- `-c:a aac`: Use AAC codec for audio
- `-shortest`: End when the shortest input stream ends (usually the audio)
- `-y`: Overwrite output file if it exists

## 4. Concatenate Video Segments

Concatenates multiple video segments using a file list:

```bash
ffmpeg -f concat -safe 0 -i concat.txt -c copy -y output.mp4
```

Where `concat.txt` contains:
```
file 'segment1.mp4'
file 'segment2.mp4'
file 'segment3.mp4'
```

Parameters:
- `-f concat`: Use concat demuxer
- `-safe 0`: Disable safety checks for file paths
- `-i concat.txt`: Input file with list of segments
- `-c copy`: Copy codec (no re-encoding to preserve quality)
- `-y`: Overwrite output file if it exists

## 5. Add Watermark Overlay

Adds a watermark image to the video:

```bash
ffmpeg -i input.mp4 -i logo.png -filter_complex "[0:v][1:v]overlay=10:10" -c:a copy -y output.mp4
```

Parameters:
- `-i input.mp4`: Input video file
- `-i logo.png`: Input watermark image
- `-filter_complex "[0:v][1:v]overlay=10:10"`: Overlay the second input (logo) onto the first input at position x=10, y=10
- `-c:a copy`: Copy audio codec (no re-encoding)
- `-y`: Overwrite output file if it exists

## 6. Get Video Information

Command to get video information (used to extract duration, resolution, etc.):

```bash
ffmpeg -i input.mp4 -f null -
```

This command attempts to output to null device, which causes FFmpeg to show information about the input file in the error output (stderr). 