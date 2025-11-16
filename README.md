# 🎨 Media Gallery Launcher

**Drop-in executable that instantly launches a beautiful HTTPS gallery for any folder**

[![Build](https://github.com/yourusername/media-gallery-launcher/actions/workflows/build.yml/badge.svg)](https://github.com/yourusername/media-gallery-launcher/actions)
[![Release](https://img.shields.io/github/v/release/yourusername/media-gallery-launcher)](https://github.com/yourusername/media-gallery-launcher/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ Features

- 🚀 **Single Executable** - No installation, just drop and run
- 🔒 **HTTPS** - Automatic self-signed certificate generation
- 🎨 **Beautiful UI** - Modern dark theme with smooth animations
- 📱 **Responsive** - Works on desktop, tablet, and mobile
- ⚡ **Fast** - Lazy loading, infinite scroll, masonry layout
- 🎬 **Video Support** - MP4, WebM, OGG with autoplay
- 🖱️ **Custom Gestures** - Mouse controls for rapid browsing
- 🔀 **Smart Shuffle** - Prioritizes unviewed items
- 📁 **Folder Organization** - Automatic subfolder detection
- 🎯 **Slideshow Mode** - Auto-advance with adjustable timing
- ⌨️ **Keyboard Shortcuts** - Full keyboard navigation

## 📦 Installation

### Download Pre-built Binary

Download the latest release for your platform:

- [Windows (x64)](https://github.com/yourusername/media-gallery-launcher/releases/latest/download/MediaGallery.exe)
- [Windows (ARM64)](https://github.com/yourusername/media-gallery-launcher/releases/latest/download/MediaGallery-arm64.exe)
- [Linux (x64)](https://github.com/yourusername/media-gallery-launcher/releases/latest/download/MediaGallery-linux)
- [macOS (Intel)](https://github.com/yourusername/media-gallery-launcher/releases/latest/download/MediaGallery-mac-intel)
- [macOS (M1/M2)](https://github.com/yourusername/media-gallery-launcher/releases/latest/download/MediaGallery-mac-m1)

### Build from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/media-gallery-launcher.git
cd media-gallery-launcher

# Build Go server
cd server
go build -o ../MediaGallery

# Or use the build script
chmod +x scripts/build.sh
./scripts/build.sh
```

## 🚀 Usage

### Quick Start

1. Copy `MediaGallery.exe` to any folder containing images/videos
2. Double-click the executable
3. Your browser opens automatically at `https://localhost:8443`
4. Accept the self-signed certificate warning

### Folder Structure Support

The gallery automatically organizes files by subfolder:

```
my-photos/
├── MediaGallery.exe
├── vacation/
│   ├── beach.jpg
│   └── sunset.png
└── family/
    └── reunion.mp4
```

Use the folder dropdown to filter by subfolder!

## ⌨️ Keyboard Shortcuts

**Gallery View:**
- `Scroll` - Load more images

**Fullscreen View:**
- `←/→` or `A/D` - Navigate between images
- `Space` - Play/Pause slideshow
- `Escape` - Exit fullscreen
- `Home/End` - Jump to first/last image

**Mouse Gestures:**
- `Left Click` - Next image
- `Right Click` - Previous image
- `Mouse Wheel` - Adjust slideshow speed

## 🎨 Supported Formats

**Images:**
- JPG, JPEG
- PNG
- WebP
- GIF
- BMP
- SVG

**Videos:**
- MP4
- WebM
- OGG
- MOV
- AVI

## 🔧 Advanced Usage

### Command Line Options

```bash
# Specify custom port
./MediaGallery --port 9443

# Disable auto-browser launch
./MediaGallery --no-browser

# Custom media directory
./MediaGallery --dir /path/to/media
```

### API Endpoints

The server exposes a simple API:

```bash
# Get file list with metadata
GET https://localhost:8443/api/files

# Health check
GET https://localhost:8443/api/health
```

### Docker Deployment

Run as a server for remote access:

```bash
docker run -d \
  -p 8443:8443 \
  -v /path/to/media:/media \
  ghcr.io/yourusername/media-gallery-launcher:latest
```

## 🛠️ Development

### Prerequisites

- Go 1.21+
- GCC (for Windows C launcher)
- UPX (optional, for compression)

### Project Structure

```
media-gallery-launcher/
├── .github/workflows/    # CI/CD pipelines
├── server/              # Go HTTPS server
│   ├── main.go
│   └── go.mod
├── web/                 # Frontend assets
│   ├── index.html
│   ├── masonry.pkgd.min.js
│   └── imagesloaded.pkgd.min.js
├── launcher/            # C launcher wrapper
│   ├── launcher.c
│   └── resource.rc
└── scripts/             # Build scripts
```

### Building

```bash
# Build server only
cd server
go build -o server

# Build with launcher (Windows)
cd launcher
./build.sh

# Full release build
./scripts/release.sh
```

### Testing

```bash
# Run tests
go test ./...

# Test with sample data
cd test-data
../MediaGallery
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

- [Masonry](https://masonry.desandro.com/) - Cascading grid layout
- [imagesLoaded](https://imagesloaded.desandro.com/) - Image loading detection
- Inspired by local photo viewers and media servers

## 🐛 Known Issues

- Self-signed certificate warnings in browsers (expected behavior)
- Some browsers may block autoplay videos (browser security feature)
- Large folders (1000+ files) may take a moment to index

## 📊 Roadmap

- [ ] Thumbnail caching
- [ ] EXIF data display
- [ ] Image editing tools
- [ ] Sharing links
- [ ] Multi-user support
- [ ] Mobile app

## 💬 Support

- 🐛 [Report Bug](https://github.com/yourusername/media-gallery-launcher/issues)
- 💡 [Request Feature](https://github.com/yourusername/media-gallery-launcher/issues)
- 💬 [Discussions](https://github.com/yourusername/media-gallery-launcher/discussions)

---

Made with ❤️ for photographers, content creators, and media enthusiasts
