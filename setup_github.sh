#!/bin/bash

echo "🚀 Setting up GitHub repository for Factual"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "README.md" ] || [ ! -f "MVP/factual/factual_pipeline.py" ]; then
    echo "❌ Error: Please run this script from the Factual project root directory"
    exit 1
fi

echo "✅ Project structure verified"

# Instructions for creating GitHub repository
echo ""
echo "📋 Manual Steps to Create GitHub Repository:"
echo "=============================================="
echo ""
echo "1. Go to https://github.com/new"
echo "2. Repository name: factual"
echo "3. Description: AI-powered social media fact-checking pipeline"
echo "4. Make it Public (recommended) or Private"
echo "5. DO NOT initialize with README (we already have one)"
echo "6. Click 'Create repository'"
echo ""
echo "After creating the repository, run these commands:"
echo "=============================================="
echo ""
echo "git remote add origin https://github.com/bluzername/factual.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "Or if you prefer SSH:"
echo "git remote add origin git@github.com:bluzername/factual.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""

# Check if remote already exists
if git remote get-url origin >/dev/null 2>&1; then
    echo "✅ Remote 'origin' already configured:"
    git remote get-url origin
    echo ""
    echo "To push to GitHub:"
    echo "git push -u origin main"
else
    echo "ℹ️  No remote configured yet. Follow the steps above."
fi

echo ""
echo "🎉 Repository setup complete!"
echo ""
echo "Next steps:"
echo "1. Create the repository on GitHub (see steps above)"
echo "2. Add the remote and push (see commands above)"
echo "3. Set up GitHub Pages (optional):"
echo "   - Go to Settings > Pages"
echo "   - Source: Deploy from a branch"
echo "   - Branch: main, folder: / (root)"
echo ""
echo "4. Enable Issues and Discussions for community engagement"
echo ""
echo "📚 Documentation will be available at:"
echo "https://github.com/bluzername/factual" 