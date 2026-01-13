# Muxxy - MKV Subtitle and Font Muxing Tool

A Python tool that automatically muxes subtitle files, font attachments, chapters, and tags into MKV video files.

**Version 2.0** - Now with a modern GUI!

## Features

- **Modern PyQt6 GUI** with intuitive three-panel layout
- **Intelligent episode matching** using fuzzy matching and confidence scoring
- **Manual override support** - easily fix incorrect matches via dropdown selection
- **Batch operations** with parallel processing for faster muxing
- **Automatic subtitle resampling** to match video resolution
- **Font detection and attachment** from subtitle directories
- **Chapter and tag file support**
- **CLI mode** with all original features plus new enhancements
- **Cross-platform** support (Linux, macOS, Windows)

## Installation

### Requirements

- Python 3.8+
- `mkvmerge` (part of MKVToolNix)
- `ffprobe` (part of FFmpeg)

```bash
# Debian/Ubuntu
sudo apt-get install mkvtoolnix ffmpeg

# Arch Linux
sudo pacman -S mkvtoolnix ffmpeg

# macOS (using Homebrew)
brew install mkvtoolnix ffmpeg

# NixOS (using provided shell.nix)
nix-shell
```

### Python Dependencies

This project uses [UV](https://github.com/astral-sh/uv) for fast dependency management:

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd muxxy
uv sync
```

**Alternative (using pip):**
```bash
pip install -r requirements.txt
```

## Usage

### GUI Mode (Recommended)

Launch the graphical interface by running without arguments:

```bash
uv run python main.py
# or with activated venv:
# python main.py
```

**GUI Workflow:**
1. **Open Directory** - Select folder containing videos and subtitles
2. **Select Videos** - Choose videos to process in left panel
3. **Match Files** - Automatically match videos to subtitles
4. **Review Matches** - Check confidence scores (color-coded)
5. **Manual Override** - Fix any incorrect matches via dropdowns
6. **Configure** - Adjust settings if needed (Edit → Settings)
7. **Start Muxing** - Begin batch processing

**GUI Features:**
- Color-coded confidence indicators (green = high, yellow = medium, red = low)
- Manual match override for any video-subtitle pair
- Progress tracking with cancellation support
- Persistent settings and window layout

### Command-Line Interface (CLI)

For scripting or automation, use CLI mode by passing arguments:

```bash
uv run python main.py [options]
# or: python main.py [options]
```

#### New CLI Features (v2.0)

```bash
# Preview matches before muxing (NEW!)
uv run python main.py --preview --dir /path/to/videos

# Adjust confidence threshold (NEW!)
uv run python main.py --confidence-threshold 0.8

# Parallel batch processing (NEW!)
uv run python main.py --batch --workers 8 --tag "MyGroup"
```

#### Command-line Arguments

| Argument | Description |
|----------|-------------|
| `--tag`, `-t` | Release tag for output filename (default: 'MySubs') |
| `--dir`, `-d` | Directory to search for MKV files (default: current) |
| `--video-track` | Custom name for video tracks |
| `--sub-track` | Custom name for subtitle tracks |
| `--lang`, `-l` | Force subtitle language code (e.g., eng, jpn) |
| `--force`, `-f` | Force muxing of ALL subtitle files in folder |
| `--all-match`, `-a` | Include all matching subtitles, not just first |
| `--debug` | Enable debug output for troubleshooting |
| `--strict` | Use strict episode number matching |
| `--no-resample` | Skip resampling of ASS subtitles |
| `--force-resample` | Force resampling even when resolutions match |
| `--shift-frames` | Shift subtitles by specified frames |
| `--output-dir` | Specify output directory for muxed files |
| **`--preview`** | **Preview matches without executing** *(NEW)* |
| **`--confidence-threshold`** | **Min confidence for auto-match (0-1)** *(NEW)* |
| **`--batch`** | **Enable parallel batch processing** *(NEW)* |
| **`--workers`** | **Number of parallel workers** *(NEW)* |

#### CLI Examples

```bash
# Basic usage with custom tag
uv run python main.py --tag "MyGroup" --dir /path/to/videos

# Preview matches first
uv run python main.py --preview --confidence-threshold 0.7

# Process with English subtitles, parallel mode
uv run python main.py --batch --workers 8 --lang eng --tag "MySubs"

# Debug matching issues
uv run python main.py --debug --preview
```

## How It Works

### Enhanced Episode Matching (v2.0)

Muxxy now uses **intelligent fuzzy matching** instead of requiring exact filenames:

**Matching Priority:**
1. **Exact filename match** (confidence: 100%)
2. **Episode/season number match** (confidence: 60-95%)
   - Supports formats: `S01E05`, `1x05`, `[05]`, `- 05`, `E05`
   - Boosts confidence with show name similarity
3. **Fuzzy show name match** (confidence: 50-70%, when no episode info)

**Example Matches:**
- `[GroupA] Anime Title - 05 [1080p].mkv` ✅ matches `[GroupB] Anime.Title.E05.ass`
- `Show.Name.S01E03.mkv` ✅ matches `show_name_03.srt`
- `Video 1x12.mkv` ✅ matches `[12].ass`

**Confidence Scores:**
- **90-100%**: High confidence (green) - auto-mux recommended
- **70-89%**: Medium confidence (yellow) - review suggested
- **Below 70%**: Low confidence (orange/red) - manual override recommended

### Output Filename Format

```
[Tag] Title - 01 [Source Resolution Codec AudioCodec].mkv
```

Example: `[MySubs] Anime Title - 05 [BDRip 1080p HEVC OPUS].mkv`

## Configuration

Settings are stored in `~/.config/muxxy/config.json` and include:
- Default release tag
- Output directory preference
- Confidence threshold
- Track naming defaults
- Resampling options
- Window size and position

## Development

See [AGENTS.md](AGENTS.md) for:
- Project architecture
- Module organization  
- Development guidelines
- Contributing information

## What's New in v2.0

- ✨ **Modern PyQt6 GUI** - Intuitive three-panel interface
- 🎯 **Smart Episode Matching** - Fuzz matching with confidence scores
- ✏️ **Manual Override** - Fix incorrect matches easily
- ⚡ **Parallel Processing** - Batch mode with 4x speed improvement
- 💾 **Persistent Config** - Saves all your preferences
- 🔍 **Match Preview** - See matches before processing
- 📊 **Confidence Indicators** - Color-coded match quality

## Troubleshooting

### GUI won't launch
```bash
# Reinstall PyQt6
uv pip install --force-reinstall PyQt6
```

### Import errors
```bash
# Make sure to use uv run
uv run python main.py

# Or activate the venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
python main.py
```

### Low match quality
```bash
# Enable debug mode to see matching details
uv run python main.py --debug --preview

# Lower confidence threshold
uv run python main.py --confidence-threshold 0.5
```

### No matches found
- Ensure subtitle files have episode numbers in filename
- Try `--debug` to see what the matcher is finding
- Use GUI for manual override

## License

MIT License

---

**Upgrade from v1.x:** The TUI has been replaced with a modern GUI. CLI functionality is preserved and enhanced. See the walkthrough for migration details.