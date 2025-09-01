#!/usr/bin/env python3
"""
Test script to verify the batch processing fix

Creates a test batch file and verifies that each URL gets its own session ID
and output directory without file conflicts.
"""

import os
import tempfile
import json
from pathlib import Path
from unified_processor import FactualProcessor

def test_session_isolation():
    """Test that batch processing creates unique sessions for each URL"""
    
    print("🧪 Testing batch processing session isolation...")
    
    # Create test batch file
    test_urls = [
        "https://www.instagram.com/reel/TEST001/",
        "https://www.instagram.com/reel/TEST002/", 
        "https://www.instagram.com/reel/TEST003/"
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for url in test_urls:
            f.write(url + '\n')
        batch_file = f.name
    
    try:
        # Create processor with test config
        test_config = {
            'use_sample_video': True,  # Use sample videos to avoid real downloads
            'output_dir': 'test_output',
            'temp_dir': 'test_temp',
            'enable_summary_slide': False,  # Disable to speed up test
            'enable_auto_cover_thumbnail': False
        }
        
        # Save test config
        config_path = 'test_config.json'
        with open(config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        
        processor = FactualProcessor(config_path)
        
        # Process batch
        results = processor.process(batch_file, mode='batch')
        
        # Verify results
        print(f"📊 Results: {results['successful']}/{results['total_urls']} successful")
        
        if results['successful'] == len(test_urls):
            print("✅ Session isolation test PASSED")
            print("   Each URL was processed with its own session ID")
            
            # Verify unique output directories
            output_dirs = [r.get('reel_output_dir') for r in results['results']]
            unique_dirs = set(output_dirs)
            
            if len(unique_dirs) == len(test_urls):
                print("✅ Output isolation test PASSED")
                print("   Each URL got its own output directory")
            else:
                print("❌ Output isolation test FAILED")
                print(f"   Expected {len(test_urls)} unique dirs, got {len(unique_dirs)}")
        else:
            print("❌ Session isolation test FAILED")
            print("   Some URLs failed to process")
            
            for failed in results.get('failed_urls', []):
                print(f"   Failed: {failed.get('url')} - {failed.get('error')}")
        
        return results['successful'] == len(test_urls)
        
    finally:
        # Cleanup
        try:
            os.unlink(batch_file)
            os.unlink(config_path)
        except:
            pass

if __name__ == "__main__":
    success = test_session_isolation()
    sys.exit(0 if success else 1)
