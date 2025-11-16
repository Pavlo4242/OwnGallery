#!/bin/bash
set -e

echo "🔨 Building Media Gallery for all platforms..."

# Build for different platforms
platforms=("windows/amd64" "windows/arm64" "linux/amd64" "darwin/amd64" "darwin/arm64")

for platform in "${platforms[@]}"; do
    split=(${platform//\// })
    GOOS=${split[0]}
    GOARCH=${split[1]}
    
    output_name="MediaGallery-$GOOS-$GOARCH"
    if [ "$GOOS" = "windows" ]; then
        output_name="$output_name.exe"
    fi
    
    echo "Building $output_name..."
    cd server
    CGO_ENABLED=0 GOOS=$GOOS GOARCH=$GOARCH go build -ldflags="-s -w" -o ../$output_name .
    cd ..
    
    echo "✅ Built: $output_name"
done

echo "🎉 All builds completed!"
