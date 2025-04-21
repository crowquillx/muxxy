# Muxxy - MKV Subtitle and Font Muxing Tool

A Python script that automatically muxes subtitle files, font attachments, chapters, and tags into MKV video files.

## Features

- Automatically pairs video files with matching subtitles by filename or episode numbers
- Resamples ASS subtitles to match video resolution 
- Finds and attaches fonts from subtitle directories
- Supports chapter files and tag files
- Handles multiple subtitle naming conventions
- Creates organized output files with proper naming

## Installation

### Requirements

- Python 3.6+
- `mkvmerge` (part of MKVToolNix)
- `ffprobe` (part of FFmpeg)
- `ass` Python library

```bash
# Debian/Ubuntu
sudo apt-get install mkvtoolnix ffmpeg
pip install ass

# Arch Linux
sudo pacman -S mkvtoolnix ffmpeg
pip install ass

# macOS (using Homebrew)
brew install mkvtoolnix ffmpeg
pip install ass
```

## Usage

```bash
python mux.py [options]
```

### Basic Usage

Simply running `python mux.py` will:
1. Find all MKV files in the current directory and subdirectories
2. Match each MKV with appropriate subtitles, fonts, chapters, and tags
3. Resample ASS subtitles to match video resolution
4. Create new files with format: `[Tag] Show - E01 [Video Params].mkv`

### Command-line Arguments

| Argument | Description |
|----------|-------------|
| `--tag`, `-t` | Release tag to use in output filename (default: 'MySubs') |
| `--dir`, `-d` | Directory to search for MKV files (default: current directory) |
| `--video-track` | Custom name for video tracks |
| `--sub-track` | Custom name for subtitle tracks |
| `--lang`, `-l` | Force a specific subtitle language code (e.g., eng, jpn) |
| `--force`, `-f` | Force muxing of ALL subtitle files in the folder |
| `--all-match`, `-a` | Include all matching subtitles, not just the first one |
| `--debug` | Enable debug output for troubleshooting |
| `--filenames` | Print all MKV and subtitle filenames found and exit |
| `--strict` | Use strict episode number matching |
| `--no-resample` | Skip resampling of ASS subtitles |
| `--force-resample` | Force resampling even when resolutions match |
| `--shift-frames` | Shift subtitles by specified frames (positive = delay, negative = advance) |
| `--output-dir` | Specify an output directory for muxed files |

### Examples

```bash
# Basic usage with custom release tag
python mux.py --tag "MyGroup"

# Process files in a specific directory
python mux.py --dir "/path/to/videos"

# Force English language for subtitles
python mux.py --lang eng

# Troubleshooting subtitle matching
python mux.py --debug --filenames
```

## Directory Structure

Muxxy works with various directory structures, but ideally:

```
Directory/
├── Video.mkv
├── Video.ass (or Video.eng.ass)
├── fonts/
│   └── *.ttf/otf
├── chapters.xml (optional)
└── tags.xml (optional)
```

Fonts can be in a `fonts/` or `attachments/` directory, or directly alongside the subtitle.

## License

MIT License