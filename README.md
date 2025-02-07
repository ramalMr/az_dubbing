```markdown name=README.md
# AI Video Dubbing System
> Professional AI-powered video dubbing system that automatically transcribes, translates and generates natural-sounding voice-overs in multiple languages.

[![Version](https://img.shields.io/badge/version-0.1.0--beta-orange)](https://github.com/ramalMr/az_dubbing)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Last Updated](https://img.shields.io/badge/last%20updated-2025--02--07-brightgreen.svg)](https://github.com/ramalMr/az_dubbing)

## 📖 Overview

AI Video Dubbing System is a comprehensive solution for automated video dubbing and translation. It uses state-of-the-art AI models for speech recognition, translation, and voice synthesis to produce high-quality dubbed videos with natural-sounding voices.

### Key Features

- 🎯 Automatic speech recognition using OpenAI's Whisper
- 🌍 Neural machine translation
- 🗣️ Natural text-to-speech with Edge-TTS
- 🎬 Professional subtitle generation
- 🎨 Advanced audio synchronization
- 🔊 Multi-language support
- 📊 Comprehensive logging

## 🛠 Technical Specifications

### Supported Formats & Codecs

#### Video
- **Input Formats**: MP4, MKV, AVI, MOV, WebM
- **Output Format**: MP4 (H.264)
- **Resolution**: Up to 4K (3840x2160)
- **Frame Rate**: Up to 60fps
- **Codecs**: H.264/AVC, H.265/HEVC
- **Bit Rate**: Variable (500k-8000k)

#### Audio
- **Sample Rate**: 16kHz/44.1kHz/48kHz
- **Formats**: WAV, MP3, AAC
- **Channels**: Mono/Stereo
- **Bit Depth**: 16/24-bit
- **Bitrate**: 128k-320k

#### Subtitles
- **Formats**: SRT, SSA/ASS
- **Encoding**: UTF-8/UTF-16
- **Styling**: Full ASS style support

### Language Support

| Language    | Speech Recognition | Translation | TTS Voices |
|------------|-------------------|-------------|------------|
| Azerbaijani | ✓                | ✓           | 2         |
| English     | ✓                | ✓           | 4         |
| Turkish     | ✓                | ✓           | 2         |

## 💻 Installation

### Prerequisites

```bash
# System Requirements
- CPU: 4+ cores recommended
- RAM: 8GB+ recommended
- GPU: NVIDIA CUDA-capable (optional)
- Storage: 2GB+ free space
- OS: Windows 10+/Ubuntu 20.04+/macOS 11+

# Required Software
- Python 3.9+
- FFmpeg
- NVIDIA CUDA Toolkit (for GPU support)
```

### Setup

```bash
# Clone repository
git clone https://github.com/ramalMr/az_dubbing.git
cd az_dubbing

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install FFmpeg
# Windows
choco install ffmpeg
# Linux
sudo apt install ffmpeg
# Mac
brew install ffmpeg
```

## 🚀 Usage

### Basic Commands

```bash
# Simple dubbing
python scripts/dub_video.py input.mp4 -o output/

# GPU-accelerated processing
python scripts/dub_video.py input.mp4 -o output/ --gpu

# Custom language and voice
python scripts/dub_video.py input.mp4 -o output/ \
    --language az \
    --voice az-AZ-BabekNeural
```

### Advanced Options

```bash
# High quality processing
python scripts/dub_video.py input.mp4 -o output/ \
    --quality high \
    --video-bitrate 2M \
    --audio-bitrate 192k \
    --subtitle-style modern

# Performance optimization
python scripts/dub_video.py input.mp4 -o output/ \
    --gpu \
    --batch-size 32 \
    --gpu-threads 2 \
    --chunk-duration 30
```

## ⚙️ Configuration

### Core Settings (config/config.json)

```json
{
    "transcriber": {
        "whisper_model": "base",
        "sample_rate": 16000,
        "chunk_duration": 30
    },
    "tts": {
        "voices": {
            "male": {
                "az": "az-AZ-BabekNeural"
            }
        },
        "sample_rate": 44100
    },
    "video": {
        "codec": "libx264",
        "crf": 23,
        "preset": "medium"
    }
}
```

### Quality Presets

| Preset | Video Bitrate | Audio Bitrate | CRF | CPU Usage |
|--------|--------------|---------------|-----|-----------|
| low    | 1000k       | 128k         | 28  | Low      |
| medium | 2000k       | 192k         | 23  | Medium   |
| high   | 4000k       | 320k         | 18  | High     |

## 📊 Performance

### Hardware Requirements

| Feature           | Minimum              | Recommended          |
|------------------|----------------------|---------------------|
| CPU              | 4 cores             | 8+ cores           |
| RAM              | 4GB                 | 16GB               |
| GPU              | -                   | NVIDIA GTX 1660+   |
| Storage          | 1GB                 | 5GB+               |
| Network          | 5 Mbps             | 20+ Mbps           |

### Processing Times (1080p 5min video)

| Hardware Setup   | Processing Time |
|-----------------|----------------|
| CPU Only        | ~15 minutes    |
| CPU + GPU       | ~5 minutes     |
| High-End GPU    | ~2 minutes     |

## 🔧 Troubleshooting

### Common Issues

1. **GPU Memory Errors**
```bash
# Solution: Reduce batch size
python scripts/dub_video.py input.mp4 -o output/ --gpu --batch-size 16
```

2. **Audio Sync Issues**
```bash
# Solution: Adjust chunk duration
python scripts/dub_video.py input.mp4 -o output/ --chunk-duration 20
```

3. **FFmpeg Errors**
```bash
# Verify installation
ffmpeg -version
```

## 📈 Monitoring

### Log Files
```bash
# View latest log
tail -f logs/video_dubbing_latest.log

# Search errors
grep "ERROR" logs/video_dubbing_*.log
```

### Performance Metrics
- CPU/GPU usage
- Memory consumption
- Processing speed
- Quality metrics

## 🔄 Version History

### v0.1.0-beta (2025-02-07)
- Initial release with core functionality
- Support for AZ, EN, TR languages
- Basic GPU acceleration
- Command-line interface

## 📝 Metadata

- **Version**: 0.1.0-beta
- **Build**: 20250207.1
- **Last Updated**: 2025-02-07 03:18:07 UTC
- **Developer**: ramalMr
- **Environment**: Python 3.9+
- **Status**: Beta Testing
```

This README.md əhatə edir:
1. Texniki spesifikasiyalar
2. Dəstəklənən formatlar
3. Hardware tələbləri
4. Performance göstəriciləri
5. Ətraflı quraşdırma təlimatları
6. Troubleshooting məlumatları
7. Monitoring imkanları
8. Version məlumatları
9. Metadata