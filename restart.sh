#!/bin/bash

# Audio Downloader Docker Compose Restart Script

echo "🔄 Restarting Audio Downloader..."
echo ""

# Stop and remove containers
echo "📦 Stopping containers..."
docker compose down

# Build the image
echo ""
echo "🔨 Building image..."
docker compose build

# Start containers in detached mode
echo ""
echo "🚀 Starting containers..."
docker compose up -d

# Follow the logs
echo ""
echo "📋 Following logs (press Ctrl+C to exit)..."
docker compose logs -f