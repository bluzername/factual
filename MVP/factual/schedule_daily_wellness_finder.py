#!/usr/bin/env python3
"""
schedule_daily_wellness_finder.py

Daily scheduler for the trending wellness reels finder.
Runs the wellness finder daily, archives results, and manages output files.

Usage:
  # Run once
  python3 schedule_daily_wellness_finder.py

  # Run as daemon (keeps running and schedules daily execution)
  python3 schedule_daily_wellness_finder.py --daemon

  # Run with custom schedule (cron format)
  python3 schedule_daily_wellness_finder.py --cron "0 18 * * *"  # Daily at 6 PM
"""

import os
import sys
import time
import argparse
import subprocess
import schedule
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
import shutil

# ─── CONFIG ───────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
WELLNESS_FINDER_SCRIPT = SCRIPT_DIR / "trending_wellness_reels_finder.py"
ARCHIVE_DIR = SCRIPT_DIR / "wellness_reels_archive"
LOG_FILE = SCRIPT_DIR / "wellness_finder_scheduler.log"

# Default configuration
DEFAULT_CONFIG = {
    "max_reels": 20,
    "min_views": 10000,
    "min_likes": 500,
    "min_comments": 50,
    "output_format": "links",
    "schedule_time": "18:00",  # 6 PM
    "archive_days": 30,  # Keep archives for 30 days
    "notification_webhook": None  # Optional webhook for notifications
}

# ─── LOGGING SETUP ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def load_config(config_file: Path = None) -> dict:
    """Load configuration from file or use defaults."""
    if config_file and config_file.exists():
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
            config = DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
        except Exception as e:
            logger.warning(f"Failed to load config from {config_file}: {e}")
    
    return DEFAULT_CONFIG.copy()

def save_config(config: dict, config_file: Path = None):
    """Save configuration to file."""
    if not config_file:
        config_file = SCRIPT_DIR / "wellness_finder_config.json"
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {config_file}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_file}: {e}")

def setup_archive_directory():
    """Create archive directory if it doesn't exist."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    logger.info(f"Archive directory: {ARCHIVE_DIR}")

def generate_output_filename(timestamp: datetime = None) -> str:
    """Generate timestamped output filename."""
    if not timestamp:
        timestamp = datetime.now()
    return f"trending_wellness_reels_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"

def run_wellness_finder(config: dict) -> tuple[bool, str]:
    """Run the wellness finder script with given configuration."""
    timestamp = datetime.now()
    output_file = generate_output_filename(timestamp)
    
    cmd = [
        "python3", str(WELLNESS_FINDER_SCRIPT),
        "--max-reels", str(config["max_reels"]),
        "--output", output_file,
        "--format", config["output_format"],
        "--min-views", str(config["min_views"]),
        "--min-likes", str(config["min_likes"]),
        "--min-comments", str(config["min_comments"])
    ]
    
    logger.info(f"Running wellness finder: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Wellness finder completed successfully")
            logger.info(f"Output: {result.stdout}")
            
            # Archive the results
            archive_results(output_file, timestamp)
            
            return True, output_file
        else:
            logger.error(f"Wellness finder failed with exit code {result.returncode}")
            logger.error(f"Error: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error("Wellness finder timed out after 1 hour")
        return False, "Script timed out"
    except Exception as e:
        logger.error(f"Failed to run wellness finder: {e}")
        return False, str(e)

def archive_results(output_file: str, timestamp: datetime):
    """Archive the output files with timestamp."""
    try:
        # Create dated directory
        date_dir = ARCHIVE_DIR / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(exist_ok=True)
        
        # Move output files to archive
        output_path = SCRIPT_DIR / output_file
        if output_path.exists():
            archived_path = date_dir / output_file
            shutil.move(str(output_path), str(archived_path))
            logger.info(f"Archived: {output_file} -> {archived_path}")
            
            # Also archive any additional output files (CSV, JSON)
            base_name = output_file.replace('.txt', '')
            for ext in ['.csv', '.json']:
                additional_file = SCRIPT_DIR / f"{base_name}{ext}"
                if additional_file.exists():
                    archived_additional = date_dir / f"{base_name}{ext}"
                    shutil.move(str(additional_file), str(archived_additional))
                    logger.info(f"Archived: {additional_file.name} -> {archived_additional}")
        
        # Create symlink to latest results
        create_latest_symlink(archived_path)
        
    except Exception as e:
        logger.error(f"Failed to archive results: {e}")

def create_latest_symlink(archived_path: Path):
    """Create symlink to the latest results."""
    try:
        latest_link = SCRIPT_DIR / "latest_trending_wellness_reels.txt"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        
        # Create relative symlink
        rel_path = os.path.relpath(archived_path, SCRIPT_DIR)
        latest_link.symlink_to(rel_path)
        logger.info(f"Created latest symlink: {latest_link} -> {rel_path}")
        
    except Exception as e:
        logger.error(f"Failed to create latest symlink: {e}")

def cleanup_old_archives(days: int = 30):
    """Remove archive directories older than specified days."""
    if not ARCHIVE_DIR.exists():
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    removed_count = 0
    
    try:
        for date_dir in ARCHIVE_DIR.iterdir():
            if date_dir.is_dir():
                try:
                    # Parse directory name as date
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        shutil.rmtree(date_dir)
                        removed_count += 1
                        logger.info(f"Removed old archive: {date_dir}")
                except ValueError:
                    # Skip directories that don't match date format
                    continue
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old archive directories")
        
    except Exception as e:
        logger.error(f"Failed to cleanup old archives: {e}")

def send_notification(success: bool, output_file: str = None, error: str = None):
    """Send notification about job completion (if webhook configured)."""
    # Placeholder for notification system
    # Could integrate with Slack, Discord, email, etc.
    pass

def daily_job():
    """The daily job that runs the wellness finder."""
    logger.info("=== Starting daily wellness reels finder job ===")
    
    # Load configuration
    config = load_config()
    
    # Setup archive directory
    setup_archive_directory()
    
    # Cleanup old archives
    cleanup_old_archives(config.get("archive_days", 30))
    
    # Run the wellness finder
    success, result = run_wellness_finder(config)
    
    # Send notification if configured
    if success:
        send_notification(True, result)
        logger.info(f"=== Daily job completed successfully: {result} ===")
    else:
        send_notification(False, error=result)
        logger.error(f"=== Daily job failed: {result} ===")
    
    logger.info("=== Daily wellness reels finder job finished ===\n")

def setup_schedule(schedule_time: str = "18:00"):
    """Setup the daily schedule."""
    try:
        schedule.every().day.at(schedule_time).do(daily_job)
        logger.info(f"Scheduled daily wellness finder at {schedule_time}")
    except Exception as e:
        logger.error(f"Failed to setup schedule: {e}")
        raise

def run_daemon():
    """Run as daemon, executing scheduled jobs."""
    logger.info("Starting wellness finder scheduler daemon...")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler daemon stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler daemon: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying

def main():
    parser = argparse.ArgumentParser(
        description="Daily scheduler for trending wellness reels finder"
    )
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run as daemon (keeps running and schedules daily execution)"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the wellness finder once and exit"
    )
    parser.add_argument(
        "--schedule-time",
        default="18:00",
        help="Daily schedule time in HH:MM format (default: 18:00)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--create-config",
        action="store_true",
        help="Create default configuration file and exit"
    )
    parser.add_argument(
        "--cleanup",
        type=int,
        help="Cleanup archives older than N days and exit"
    )
    
    args = parser.parse_args()
    
    # Create default config if requested
    if args.create_config:
        config_file = args.config or (SCRIPT_DIR / "wellness_finder_config.json")
        save_config(DEFAULT_CONFIG, config_file)
        print(f"Default configuration created: {config_file}")
        return
    
    # Cleanup old archives if requested
    if args.cleanup is not None:
        setup_archive_directory()
        cleanup_old_archives(args.cleanup)
        print(f"Cleanup completed (removed archives older than {args.cleanup} days)")
        return
    
    # Validate that wellness finder script exists
    if not WELLNESS_FINDER_SCRIPT.exists():
        logger.error(f"Wellness finder script not found: {WELLNESS_FINDER_SCRIPT}")
        sys.exit(1)
    
    # Load configuration
    config = load_config(args.config)
    config["schedule_time"] = args.schedule_time
    
    if args.run_once:
        # Run once and exit
        logger.info("Running wellness finder once...")
        setup_archive_directory()
        success, result = run_wellness_finder(config)
        if success:
            print(f"✅ Completed successfully: {result}")
        else:
            print(f"❌ Failed: {result}")
            sys.exit(1)
    
    elif args.daemon:
        # Run as daemon
        setup_schedule(config["schedule_time"])
        run_daemon()
    
    else:
        # Default: setup schedule and run once, then exit
        logger.info("Setting up schedule for daily execution...")
        setup_schedule(config["schedule_time"])
        
        # Run immediately
        daily_job()
        
        print(f"✅ Setup complete! Daily execution scheduled at {config['schedule_time']}")
        print(f"To run as daemon: python3 {__file__} --daemon")
        print(f"To run once: python3 {__file__} --run-once")

if __name__ == "__main__":
    main()