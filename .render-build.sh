#!/bin/bash
# .render-build.sh - Render build script

echo "🚀 Building Brain 3.0 for Render..."

# Install dependencies
pip install -r requirements.txt

# Install additional system dependencies
apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
mkdir -p /tmp/uploads
mkdir -p logs

echo "✅ Build complete!"
