# Factual

Fact-checking pipeline for short social videos. Give it an Instagram or Facebook reel URL and it downloads the video, transcribes it, extracts factual claims with an OpenAI model, writes corrections or confirmations with sources, narrates them with ElevenLabs TTS, and renders an enhanced mp4 with freeze-frame interventions, a summary slide, an HTML report and an Instagram-ready description.

The pipeline lives in `MVP/factual/`. The repo root also holds an optional agentic workflow that runs the pipeline in a queue and can post results to Instagram (see [Agentic Instagram workflow](#agentic-instagram-workflow)).

## Requirements

- Python 3.10 or newer
- `ffmpeg` and `ffprobe` on PATH (`brew install ffmpeg` / `apt install ffmpeg`)
- `yt-dlp` (installed by the requirements file)
- An OpenAI API key and an ElevenLabs API key
- Optional: ImageMagick for preview images, an NVIDIA GPU for the local Parakeet ASR backend

## Install

```bash
git clone https://github.com/bluzername/factual.git
cd factual
python -m venv .venv && source .venv/bin/activate
pip install -r MVP/factual/requirements.txt
cp .env.example .env   # then fill in the keys
```

Optional local ASR backends (Parakeet via NeMo, faster-whisper):

```bash
pip install -r MVP/factual/requirements_asr.txt
# or the guided installer: cd MVP/factual && ./install_parakeet.sh --download-model
```

Without them the pipeline transcribes through the OpenAI Whisper API.

## Configuration

### Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | yes | - | Claim extraction, sourcing, text condensation, Whisper API |
| `ELEVENLABS_API_KEY` | yes | - | TTS narration; validated with a live request at startup |
| `FACTUAL_LLM_MODEL` | no | `gpt-5-nano` | Primary chat model |
| `FACTUAL_LLM_MINI_MODEL` | no | `gpt-5-nano` | Cheaper model for text condensation |
| `FACTUAL_WHISPER_MODEL` | no | `whisper-1` | OpenAI transcription model |
| `FACTUAL_TTS_MODEL` | no | `eleven_flash_v2` | ElevenLabs model id |
| `ELEVENLABS_VOICE_ID` | no | `21m00Tcm4TlvDq8ikWAM` | ElevenLabs voice |
| `IG_ACCESS_TOKEN`, `IG_BUSINESS_USER_ID` | no | - | Only for `get_trending_reels_insights.py` |

Model ids are defined once in `MVP/factual/model_config.py`. The shell wrappers export `.env` automatically; when calling the Python entry points directly, export the variables first (`set -a; source .env; set +a`).

### JSON config file

Every entry point accepts `--config path.json`. Keys override `DEFAULT_CONFIG` in `factual_pipeline.py`. The ones you are most likely to change:

```json
{
  "asr_backend": "auto",
  "parakeet_device": "auto",
  "llm_model": "gpt-5-nano",
  "tts_model": "eleven_flash_v2",
  "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",
  "max_interventions": 3,
  "max_intervention_text_length": 200,
  "enable_tts_speed_adjustment": true,
  "generate_summary_slide": true,
  "watermark_path": "assets/logo_watermark.png",
  "ffmpeg_path": "ffmpeg",
  "yt_dlp_path": "yt-dlp",
  "output_dir": "output",
  "temp_dir": "temp"
}
```

`asr_backend` accepts `auto`, `parakeet`, `faster_whisper` or `openai`; `auto` picks the best installed backend and falls back to the API. API keys may also be set in the JSON file, but environment variables are preferred.

## Usage

All commands run from `MVP/factual/`.

### Recommended: unified CLI (v2)

```bash
cd MVP/factual
python factual_cli.py "https://www.instagram.com/reel/ABC123/"
python factual_cli.py --batch urls.txt
python factual_cli.py --batch urls.txt --config custom_config.json --verbose
```

`run_factual_v2.sh` wraps the same processor and also sources `.env`:

```bash
./run_factual_v2.sh "https://www.instagram.com/reel/ABC123/"
./run_factual_v2.sh --batch urls.txt [config.json]
./run_factual_v2.sh --legacy --batch urls.txt   # old single-session pipeline
```

Batch files hold one URL per line; blank lines and lines starting with `#` are ignored.

### Legacy pipeline entry point

`factual_pipeline.py` (also wrapped by `run_factual.sh`) keeps the original flags:

```bash
python factual_pipeline.py "URL" [--config cfg.json]
python factual_pipeline.py --batch urls.txt
python factual_pipeline.py --no-text --no-summary --no-slide "URL"
python factual_pipeline.py --debug-visual --debug-segments --debug-manifest "URL"   # or --debug-all
python factual_pipeline.py --use-sample "URL"   # synthetic sample video, no download
```

Note: legacy batch mode reuses one session id for every URL; use the unified CLI for batches.

### Outputs

Single runs write to `output/<timestamp>/`, batches to `output/batch_<timestamp>/NNN_<id>/`. Each reel directory contains the enhanced video, `manifest.json`, `metrics.json` (views, likes, comments via yt-dlp), an HTML summary with sources, an Instagram description, a copyable sources text file and, unless disabled, `factual_summary_slide.png` for manual insertion in an editor. Batch runs add `batch_summary.json`, `batch_summary.txt`, `batch_summary.html` and `batch_metrics.csv`.

### Other tools in `MVP/factual/`

- `setup.py` creates `assets/`, `output/`, `temp/` and a placeholder watermark (`make setup`).
- `get_trending_reels_insights.py --hashtag TAG ...` pulls reel metrics for hashtags through the Instagram Graph API into `trending_reels_insights.csv`.
- `docs/ffmpeg_commands.md` documents the ffmpeg filter graphs used, `docs/example_manifest.json` shows the manifest format.

## Agentic Instagram workflow

`agentic_workflow.py` at the repo root queues reel URLs, runs the pipeline for each, uploads the result (Cloudinary, S3 or a file-share service via `file_uploader.py`) and can publish to Instagram through the Graph API. Auto-posting is off by default.

```bash
pip install -r requirements.txt                       # pipeline plus cloudinary/boto3
python agentic_workflow.py create-config --output workflow_config.json
python agentic_workflow.py --config workflow_config.json add --file reel_urls.txt
python agentic_workflow.py --config workflow_config.json run --no-auto-post
python agentic_workflow.py --config workflow_config.json status
```

`quick_start.py` is an interactive setup wizard for the same workflow and `example_batch_runner.py` shows programmatic use. State and results land in `workflow_output/`. Full option reference: [AGENTIC_WORKFLOW_README.md](AGENTIC_WORKFLOW_README.md). `workflow_config.json` contains credentials and is git-ignored.

## Development

```bash
pip install -r MVP/factual/requirements-dev.txt
python -m pytest -rs                 # offline unit tests; integration tests skip without keys/ffmpeg/torch
ruff check .
python -m compileall -q MVP/factual
```

CI (`.github/workflows/ci.yml`) runs the same three commands on Python 3.10 and 3.12. `test_parakeet_integration.py` and `test_batch_fix.py` only run when `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `ffmpeg` and (for Parakeet) `torch` are available.

## Known limitations

- `FactualPipeline.__init__` validates the ElevenLabs key with a network call, so the pipeline cannot be constructed offline.
- `factual_pipeline.py` is a 7000-line module; the unified processor wraps it rather than replacing it.
- Instagram and Facebook downloads depend on `yt-dlp` keeping up with platform changes.
- The `speed` voice setting is only honoured by some ElevenLabs models; the pipeline retries without it on API errors.
- Two legacy unit tests are skipped because they target methods removed in the v2 refactor.

## License

MIT, see [LICENSE](LICENSE).
