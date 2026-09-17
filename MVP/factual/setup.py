#!/usr/bin/env python3
"""
Setup script for Factual pipeline.
Creates necessary directories and sample watermark image.
"""

import os
import sys
from pathlib import Path
import argparse

PYTHON_REQUIRES = (3, 10)


def check_python_version():
    """Fail fast on interpreters older than the supported minimum."""
    if sys.version_info < PYTHON_REQUIRES:
        required = ".".join(str(part) for part in PYTHON_REQUIRES)
        found = f"{sys.version_info.major}.{sys.version_info.minor}"
        sys.exit(f"Factual requires Python {required}+ (found {found})")


def main():
    check_python_version()
    parser = argparse.ArgumentParser(description="Set up the Factual pipeline environment")
    parser.add_argument("--force", action="store_true", help="Force recreation of directories and sample files")
    args = parser.parse_args()
    
    # Create directories
    directories = ["assets", "output", "temp"]
    for directory in directories:
        path = Path(directory)
        if not path.exists() or args.force:
            path.mkdir(exist_ok=True)
            print(f"Created directory: {path}")
        else:
            print(f"Directory already exists: {path}")
    
    # Create a sample watermark if it doesn't exist
    watermark_path = Path("assets/logo_watermark.png")
    if not watermark_path.exists() or args.force:
        try:
            # Generate a simple PNG watermark using Pillow
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a transparent image
            img = Image.new('RGBA', (200, 200), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw a rectangle
            draw.rectangle([(20, 20), (180, 180)], outline=(255, 255, 255, 200), width=4)
            
            # Add text
            try:
                font = ImageFont.truetype("Arial", 40)
            except IOError:
                # Use default font if Arial not available
                font = ImageFont.load_default()
            
            draw.text((100, 100), "FACT", fill=(255, 255, 255, 200), font=font, anchor="mm")
            
            # Save the image
            img.save(watermark_path)
            print(f"Created sample watermark: {watermark_path}")
            
        except ImportError:
            print("Warning: Pillow is not installed. Could not create sample watermark.")
            print("Please install Pillow or manually create a watermark image at assets/logo_watermark.png")
            print("pip install pillow")
            
            # Create a text file with instructions instead
            with open(Path("assets/WATERMARK_INSTRUCTIONS.txt"), "w") as f:
                f.write("Please add a logo_watermark.png file in this directory.\n")
                f.write("Recommended size: 200x200px with transparency.\n")
            print(f"Created instructions at: assets/WATERMARK_INSTRUCTIONS.txt")
    else:
        print(f"Watermark already exists: {watermark_path}")
    
    print("\nSetup complete!")
    print("Set OPENAI_API_KEY and ELEVENLABS_API_KEY (see .env.example) and run:")
    print("python factual_cli.py https://www.instagram.com/reel/YOUR_REEL_ID/")

if __name__ == "__main__":
    main() 