# Summary Slide Feature

The Factual pipeline now automatically generates a summary slide as a PNG image that you can manually add to your reels before uploading to Instagram.

## What is it?

The summary slide is a standalone PNG image (1080x1920 pixels, perfect for Instagram Stories/Reels) that contains:

- **Logo watermark** - Your brand logo positioned at the top center (same as video watermarks)
- **Truthfulness watermark** - Either "Verified" or "BS" watermark based on the overall truthfulness score
- **3 bullet points** summarizing the fact-checking results:
  1. Claims count and accuracy breakdown
  2. Overall truthfulness score with color coding
  3. Key finding or notable claim

## Example Output

```
FACT-CHECK SUMMARY

• 📊 3 claims checked: 2 accurate, 1 inaccurate
• 🟡 Moderate truthfulness score: 67%
• ⚠️ Key issue: Earth is only 6,000 years old
```

## How to Use

### 1. Automatic Generation
By default, the pipeline creates a summary slide for every processed reel:

```bash
./run_factual.sh https://www.instagram.com/reel/ABC123/
```

Output will include:
```
Summary slide: output/20231215143022/factual_summary_slide.png
💡 Use this PNG slide to manually add a summary to your reel before uploading!
```

### 2. Manual Addition to Your Reel
1. **Download** the generated PNG slide
2. **Import** it into your video editor (CapCut, InShot, etc.)
3. **Add** it as the final frame of your reel
4. **Adjust** timing (recommended: 3-5 seconds)
5. **Upload** to Instagram

### 3. Configuration Options

**Disable summary slide generation:**
```bash
./run_factual.sh --no-slide https://www.instagram.com/reel/ABC123/
```

**Customize slide dimensions** (in config.json):
```json
{
  "generate_summary_slide": true,
  "summary_slide_width": 1080,
  "summary_slide_height": 1920
}
```

**Disable in config:**
```json
{
  "generate_summary_slide": false
}
```

## Batch Processing

Summary slides are generated for each reel in batch processing:

```bash
./run_factual.sh --batch my_reels.txt
```

Each reel gets its own directory with a summary slide:
```
output/batch_20231215_143022/
├── 001_reel1/
│   ├── factual_output.mp4
│   └── factual_summary_slide.png
├── 002_reel2/
│   ├── factual_output.mp4
│   └── factual_summary_slide.png
└── batch_summary.txt
```

## Slide Layout

The summary slide uses a clean, professional layout:

```
┌─────────────────────────┐
│      [LOGO WATERMARK]   │ ← Top 20% (logo positioning)
│                         │
│   FACT-CHECK SUMMARY    │ ← Title
│                         │
│ • Claims breakdown...   │ ← Bullet points start at 30%
│ • Truthfulness score... │   (centered, readable font)
│ • Key finding...        │
│                         │
│                         │
│  [TRUTHFULNESS MARK]    │ ← Bottom (verified/bs watermark)
└─────────────────────────┘
```

## Watermark Selection

The truthfulness watermark is automatically selected based on your fact-checking results:

- **≥50% accurate claims** → Verified watermark (`verified_watermark_path`)
- **<50% accurate claims** → BS/Correction watermark (`bs_watermark_path`)

Make sure these watermark files exist in your assets folder.

## Color Coding

Bullet points use color-coded emojis for quick visual understanding:

- 🟢 **Green** - High truthfulness (80%+)
- 🟡 **Yellow** - Moderate truthfulness (50-79%)
- 🔴 **Red** - Low truthfulness (<50%)
- ✅ **Checkmark** - Confirmed accurate claims
- ❌ **X** - Inaccurate claims
- ⚠️ **Warning** - Key issues to highlight

## Technical Details

- **Format**: PNG with transparent background support
- **Size**: 1080x1920 pixels (Instagram Reels/Stories format)
- **Quality**: High quality (q:v 2)
- **Font**: System default, 48px for title, variable for content
- **Positioning**: Mathematically centered for perfect alignment

## Troubleshooting

### Slide not generated?
1. Check if `generate_summary_slide` is `true` in config
2. Verify FFmpeg is working properly
3. Ensure output directory is writable
4. Look for error messages in the logs

### Watermarks not showing?
1. Check watermark file paths in config.json:
   - `watermark_path` (logo)
   - `verified_watermark_path` 
   - `bs_watermark_path`
2. Ensure watermark files exist and are readable
3. Verify file formats (PNG recommended)

### Text too long?
The pipeline automatically truncates bullet points to fit properly on the slide. For very long claims, only the first part will be shown with "..." 

### Custom styling?
The slide generation uses FFmpeg's drawtext filter. Advanced users can modify the `_create_summary_slide_png` method to customize:
- Font sizes and colors
- Background colors
- Text positioning
- Watermark sizes

## Integration with Workflow

The summary slide feature seamlessly integrates with your existing workflow:

1. **Process reel** → Generates video + slide
2. **Review outputs** → Check both video and slide quality  
3. **Edit manually** → Add slide to end of video in your editor
4. **Upload to IG** → Post with professional fact-check summary

This gives you maximum control over the final presentation while automating the fact-checking analysis and summary generation. 