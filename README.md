# Factual - AI-Powered Social Media Fact-Checking Pipeline

An automated pipeline that downloads social media videos (Instagram/Facebook), extracts factual claims, generates AI-powered fact-checking interventions, and creates enhanced videos with embedded corrections and confirmations.

## 🎯 Overview

Factual automatically:
1. **Discovers** trending factual wellness content using Instagram Graph API
2. **Downloads** social media videos from Instagram/Facebook
3. **Transcribes** audio using OpenAI Whisper
4. **Extracts** factual claims using GPT-4o
5. **Generates** fact-checking commentary with sources
6. **Creates** TTS narration using ElevenLabs
7. **Produces** enhanced videos with freeze-frame interventions
8. **Outputs** source citations for credibility

## 🚀 Features

- **Trending Content Discovery**: AI-powered wellness content finder using Instagram Graph API
- **Multi-platform support**: Instagram and Facebook videos
- **AI-powered fact-checking**: Uses GPT-4o for claim identification and commentary
- **Professional TTS**: ElevenLabs integration for natural narration
- **Visual interventions**: Grayscale freeze-frames with overlaid text
- **Source citations**: Automatic generation of credible source lists
- **Batch processing**: Handle multiple URLs efficiently
- **Quality outputs**: Summary slides, previews, and manifests
- **MCP Server Interface**: API access for programmatic integration

## 📋 Requirements

- Python 3.8+
- FFmpeg
- OpenAI API key
- ElevenLabs API key
- ImageMagick (optional, for preview generation)

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/bluzername/factual.git
   cd factual
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg**:
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu**: `sudo apt install ffmpeg`
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

4. **Install ImageMagick** (optional):
   - **macOS**: `brew install imagemagick`
   - **Ubuntu**: `sudo apt install imagemagick`

## ⚙️ Configuration

1. **Copy the example config**:
   ```bash
   cp MVP/factual/docs/env.example MVP/factual/.env
   ```

2. **Edit the configuration**:
   ```bash
   nano MVP/factual/.env
   ```

3. **Set your API keys**:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ```

## 🎬 Usage

### Trending Wellness Content Discovery

**NEW**: Find trending factual wellness reels automatically:

```bash
cd MVP/factual
./run_wellness_finder.sh              # Find 20 trending wellness reels
./run_wellness_finder.sh -n 50 -f csv # Get 50 reels with detailed analysis
```

This generates a list of trending wellness reel URLs for processing:
```
trending_wellness_links.txt
```

### Single Video Processing

```bash
cd MVP/factual
./run_factual.sh "https://www.instagram.com/reel/EXAMPLE_ID/"
```

### Batch Processing

1. **Create a batch file** with URLs (one per line):
   ```txt
   https://www.instagram.com/reel/EXAMPLE1/
   https://www.instagram.com/reel/EXAMPLE2/
   https://www.facebook.com/watch?v=EXAMPLE3
   ```

2. **Run batch processing**:
   ```bash
   ./run_factual.sh --batch batch_urls.txt
   ```

3. **Process trending wellness reels**:
   ```bash
   # First discover trending content
   ./run_wellness_finder.sh
   # Then process the discovered URLs
   ./run_factual.sh --batch trending_wellness_links.txt
   ```

### Command Line Options

```bash
# Basic usage
python factual_pipeline.py "URL"

# With custom config
python factual_pipeline.py --config custom_config.json "URL"

# Debug options
python factual_pipeline.py --debug-all "URL"

# Disable features
python factual_pipeline.py --no-text --no-summary "URL"

# Use sample video for testing
python factual_pipeline.py --use-sample "URL"
```

## 📁 Output Structure

Each run creates a timestamped folder:

```
output/20250714121435/
├── factual_output.mp4          # Final enhanced video
├── factual_output.json         # Detailed manifest
├── factual_summary_slide.png   # Summary slide for manual addition
├── preview.jpg                 # Visual preview of interventions
├── sources.txt                 # Source citations for description
└── batch_summary.json          # (Batch mode only)
```

## 🔧 Configuration Options

Key configuration parameters in `config.json`:

```json
{
  "max_interventions": 4,
  "max_intervention_text_length": 250,
  "enable_tts_speed_adjustment": true,
  "render_intervention_text": true,
  "include_summary_frame": true,
  "generate_summary_slide": true
}
```

## 🎨 Customization

### Watermarks
- Place custom watermarks in `assets/`
- Configure paths in `config.json`

### Voice Settings
- Modify ElevenLabs voice ID in config
- Adjust TTS speed and quality settings

### Visual Style
- Customize intervention text formatting
- Modify freeze-frame appearance
- Adjust summary slide layout

## 🔍 Debugging

Enable debug options for troubleshooting:

```bash
# Visual checkpoints
python factual_pipeline.py --debug-visual "URL"

# Save individual segments
python factual_pipeline.py --debug-segments "URL"

# Detailed sequence manifest
python factual_pipeline.py --debug-manifest "URL"

# All debug options
python factual_pipeline.py --debug-all "URL"
```

## 📊 Example Output

### Video Structure
1. **Original content** (0:00-0:38)
2. **Factual intervention** (freeze-frame + narration)
3. **Original content** continues
4. **Additional interventions** as needed
5. **Summary frame** (optional)

### Sources.txt Format
```
- Fluoride effectively reduces dental cavities — CDC, 2023 (https://www.cdc.gov/fluoridation/)
- High fluoride exposure may pose neurotoxic risks — Harvard School of Public Health, 2022 (https://www.hsph.harvard.edu/...)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for GPT-4o and Whisper APIs
- ElevenLabs for TTS technology
- FFmpeg for video processing
- The fact-checking community for inspiration

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the [documentation](docs/)
- Review debug logs for troubleshooting

---

**Factual** - Making social media more credible, one video at a time. 