# Muxxy - MKV Subtitle and Font Muxing Tool

A Python tool that automatically muxes subtitle files, font attachments, chapters, and tags into MKV video files.

## Features

- Automatically pairs video files with matching subtitles by filename or episode numbers
- Resamples ASS subtitles to match video resolution 
- Finds and attaches fonts from subtitle directories
- Supports chapter files and tag files
- Handles multiple subtitle naming conventions
- Creates organized output files with proper naming
- Includes both CLI and interactive TUI interfaces

## Installation

### Requirements

- Python 3.6+
- `mkvmerge` (part of MKVToolNix)
- `ffprobe` (part of FFmpeg)
- `ass` Python library
- `textual` Python library (for TUI)

```bash
# Debian/Ubuntu
sudo apt-get install mkvtoolnix ffmpeg
pip install ass textual

# Arch Linux
sudo pacman -S mkvtoolnix ffmpeg
pip install ass textual

# macOS (using Homebrew)
brew install mkvtoolnix ffmpeg
pip install ass textual

# NixOS (using provided shell.nix)
nix-shell
```

## Usage

Muxxy provides two interfaces: a command-line interface (CLI) and a terminal user interface (TUI).

### Terminal User Interface (TUI)

For an interactive experience, simply run:

```bash
python main.py
```

This launches the TUI with the following features:
- **Welcome Screen**: Navigate through available options
- **File List**: Browse available MKV and subtitle files in your directory
- **Mux Options**: Configure muxing settings through a user-friendly form
- **Settings**: Configure application preferences (coming soon)

Navigate the TUI using:
- Mouse clicks on buttons and form fields
- Keyboard shortcuts shown at the bottom of each screen
- Tab to move between form fields
- Arrow keys for selection
- Enter to confirm actions

### Command-line Interface (CLI)

For scripting or batch operations, use the CLI by passing arguments:

```bash
python main.py [options]
```

### Basic CLI Usage

Running `python main.py --tag "MyTag"` will:
1. Find all MKV files in the current directory and subdirectories
2. Match each MKV with appropriate subtitles, fonts, chapters, and tags
3. Resample ASS subtitles to match video resolution
4. Create new files with format: `[MyTag] Title - 01 [BDRip 1080p HEVC OPUS].mkv`

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
python main.py --tag "MyGroup"

# Process files in a specific directory
python main.py --dir "/path/to/videos"

# Force English language for subtitles
python main.py --lang eng

# Troubleshooting subtitle matching
python main.py --debug --filenames
```

## Output Filename Format

Muxxy creates organized output files with the following naming convention:

```
[Tag] Title - 01 [Source Type Resolution BitDepth VideoCodec AudioCodec].mkv
```

The file includes:
- Your custom release tag
- Show name and episode number (extracted from source filename)
- Source type (BDRip, Web-DL, etc.)
- Resolution (1080p, 720p, etc.)
- Bit depth when applicable (10bit)
- Video codec (HEVC, h264)
- Audio codec (DTS, AAC, FLAC, etc.)

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