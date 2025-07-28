#!/usr/bin/env python3
"""
Quick Start Guide for Agentic Workflow

This script helps you get started with the agentic workflow by:
1. Checking prerequisites
2. Creating example configuration
3. Running a simple test workflow
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import asyncio

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python 3.8+ required, found {sys.version}")
    else:
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check for MVP/factual directory
    factual_dir = Path("MVP/factual")
    if not factual_dir.exists():
        issues.append("MVP/factual directory not found - ensure you're in the Factual project root")
    else:
        print("✅ MVP/factual directory found")
    
    # Check for factual pipeline
    pipeline_file = factual_dir / "factual_pipeline.py"
    if not pipeline_file.exists():
        issues.append("factual_pipeline.py not found in MVP/factual/")
    else:
        print("✅ Factual pipeline found")
    
    # Check for workflow files
    required_files = ["agentic_workflow.py", "file_uploader.py"]
    for file in required_files:
        if not Path(file).exists():
            issues.append(f"Required workflow file not found: {file}")
        else:
            print(f"✅ {file} found")
    
    if issues:
        print("\n❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    print("✅ All prerequisites met!")
    return True

def check_dependencies():
    """Check if required Python packages are installed."""
    print("\n📦 Checking Python dependencies...")
    
    required_packages = [
        "openai",
        "elevenlabs", 
        "requests",
        "Pillow",
        "numpy"
    ]
    
    optional_packages = [
        "cloudinary",
        "boto3",
        "python-dotenv"
    ]
    
    missing_required = []
    missing_optional = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_required.append(package)
            print(f"❌ {package} (required)")
    
    for package in optional_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_optional.append(package)
            print(f"⚠️  {package} (optional)")
    
    if missing_required:
        print(f"\n❌ Missing required packages: {', '.join(missing_required)}")
        print("Install with: pip install " + " ".join(missing_required))
        return False
    
    if missing_optional:
        print(f"\n⚠️  Missing optional packages: {', '.join(missing_optional)}")
        print("Install with: pip install " + " ".join(missing_optional))
        print("These are needed for file uploading and advanced features.")
    
    return True

def create_example_config():
    """Create an example configuration file."""
    print("\n⚙️  Creating example configuration...")
    
    config_path = "workflow_config.json"
    
    if Path(config_path).exists():
        response = input(f"{config_path} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Keeping existing configuration.")
            return config_path
    
    # Run the workflow config creation
    try:
        subprocess.run([
            sys.executable, "agentic_workflow.py", 
            "create-config", "--output", config_path
        ], check=True)
        print(f"✅ Created {config_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create config: {e}")
        return None
    
    return config_path

def update_config_with_user_input(config_path):
    """Help user update configuration with their API keys."""
    print(f"\n📝 Updating configuration in {config_path}...")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print("\nTo use this workflow, you'll need to add your API credentials.")
    print("You can edit the file manually or enter them now:")
    
    # OpenAI API Key
    openai_key = input("\nOpenAI API Key (press Enter to skip): ").strip()
    if openai_key:
        # Update the factual config if it exists
        factual_config_path = config.get('factual_config_path')
        if factual_config_path and Path(factual_config_path).exists():
            try:
                with open(factual_config_path, 'r') as f:
                    factual_config = json.load(f)
                factual_config['openai_api_key'] = openai_key
                with open(factual_config_path, 'w') as f:
                    json.dump(factual_config, f, indent=2)
                print(f"✅ Updated OpenAI key in {factual_config_path}")
            except Exception as e:
                print(f"⚠️  Could not update factual config: {e}")
                print("You'll need to add the OpenAI key manually to the factual pipeline config.")
    
    # ElevenLabs API Key
    elevenlabs_key = input("ElevenLabs API Key (press Enter to skip): ").strip()
    if elevenlabs_key:
        # Update the factual config if it exists
        factual_config_path = config.get('factual_config_path')
        if factual_config_path and Path(factual_config_path).exists():
            try:
                with open(factual_config_path, 'r') as f:
                    factual_config = json.load(f)
                factual_config['elevenlabs_api_key'] = elevenlabs_key
                with open(factual_config_path, 'w') as f:
                    json.dump(factual_config, f, indent=2)
                print(f"✅ Updated ElevenLabs key in {factual_config_path}")
            except Exception as e:
                print(f"⚠️  Could not update factual config: {e}")
    
    # Instagram credentials
    instagram_token = input("Instagram Access Token (press Enter to skip): ").strip()
    if instagram_token:
        config['instagram_access_token'] = instagram_token
    
    instagram_user_id = input("Instagram Business User ID (press Enter to skip): ").strip()
    if instagram_user_id:
        config['instagram_business_user_id'] = instagram_user_id
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configuration updated!")
    
    if not (openai_key and elevenlabs_key):
        print("\n⚠️  Note: You'll need to add your API keys to run the workflow.")
        print(f"Edit {config_path} and add your credentials.")

async def run_test_workflow(config_path):
    """Run a simple test workflow."""
    print("\n🧪 Running test workflow...")
    
    try:
        from agentic_workflow import AgenticWorkflow, WorkflowConfig
        
        # Load config
        config = WorkflowConfig.from_file(config_path)
        
        # Disable auto-posting for safety
        config.enable_auto_posting = False
        
        # Initialize workflow
        workflow = AgenticWorkflow(config)
        
        # Add a test URL (the working example from the pipeline)
        test_urls = ["https://www.instagram.com/reel/DE_C78HyOVM/"]
        
        print("Adding test reel to queue...")
        task_ids = workflow.add_reel_urls(test_urls)
        print(f"Added {len(task_ids)} test tasks")
        
        print("Running workflow (fact-checking only, no auto-posting)...")
        summary = await workflow.run_workflow()
        
        print("\n🎉 Test workflow completed!")
        print(f"Total tasks: {summary['total_tasks']}")
        print(f"Success rate: {summary['success_rate']:.1%}")
        print(f"Status breakdown: {summary['status_breakdown']}")
        print(f"Output directory: {summary['output_directory']}")
        
        if summary['failed_tasks']:
            print("\nFailed tasks:")
            for failed in summary['failed_tasks']:
                print(f"  {failed['url']}: {failed['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test workflow failed: {str(e)}")
        print("This might be due to missing API keys or configuration issues.")
        return False

def print_next_steps():
    """Print guidance for next steps."""
    print("\n🚀 Next Steps:")
    print("=" * 50)
    
    print("\n1. Complete API Setup:")
    print("   - Add your OpenAI API key")
    print("   - Add your ElevenLabs API key")
    print("   - Configure Instagram Graph API (for auto-posting)")
    print("   - Setup file upload service (Cloudinary/S3)")
    
    print("\n2. Test the workflow:")
    print("   python agentic_workflow.py --config workflow_config.json add --urls https://www.instagram.com/reel/DE_C78HyOVM/")
    print("   python agentic_workflow.py --config workflow_config.json run --no-auto-post")
    
    print("\n3. Process your own reels:")
    print("   python agentic_workflow.py --config workflow_config.json add --file your_reel_urls.txt")
    print("   python agentic_workflow.py --config workflow_config.json run")
    
    print("\n4. Monitor progress:")
    print("   python agentic_workflow.py --config workflow_config.json status")
    
    print("\n5. Use programmatically:")
    print("   python example_batch_runner.py")
    
    print("\n📚 Documentation:")
    print("   - Read AGENTIC_WORKFLOW_README.md for detailed usage")
    print("   - Check workflow_config.json for all configuration options")
    
    print("\n⚠️  Important:")
    print("   - Auto-posting is disabled by default for safety")
    print("   - Always test with --no-auto-post first")
    print("   - Review output before enabling auto-posting")

def main():
    """Main quick start function."""
    print("🎬 Factual Agentic Workflow - Quick Start")
    print("=" * 50)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Please fix the issues above before continuing.")
        return
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Please install missing required packages before continuing.")
        return
    
    # Create configuration
    config_path = create_example_config()
    if not config_path:
        print("\n❌ Failed to create configuration file.")
        return
    
    # Update configuration
    update_config_with_user_input(config_path)
    
    # Ask if user wants to run test
    response = input("\nWould you like to run a test workflow? (Y/n): ")
    if response.lower() != 'n':
        success = asyncio.run(run_test_workflow(config_path))
        if not success:
            print("\n⚠️  Test failed, but you can still use the workflow once API keys are configured.")
    
    # Print next steps
    print_next_steps()
    
    print("\n✅ Quick start complete!")

if __name__ == "__main__":
    main()