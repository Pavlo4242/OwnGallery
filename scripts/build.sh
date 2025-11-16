#!/bin/bash
set -e

echo "🔨 Building Media Gallery Launcher..."

# Build Go server
cd server
echo "Building server..."
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o ../MediaGallery.exe .
echo "✅ Server built: MediaGallery.exe"

cd ..

# Check size
SIZE=$(du -h MediaGallery.exe | cut -f1)
echo "📦 Binary size: $SIZE"

echo "✅ Build complete!"
echo ""
echo "To test:"
echo "  cd test-data"
echo "  ../MediaGallery.exe"
