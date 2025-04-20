# Muxxy - MKV Subtitle and Font Muxing Tool

Muxxy is a Python script that automates the process of muxing subtitle files, font attachments, chapters, and tags into MKV video files. It's particularly useful for anime and foreign films where you want to properly include subtitles with all the required fonts.

## Features

- Automatically detects and pairs video files with matching subtitles based on filename or episode numbers
- Properly resamples ASS subtitles to match video resolution using the `ass` library
- Intelligently finds and attaches fonts from the subtitle's directory
- Supports chapter files and tag files
- Recursively processes all MKV files in a directory structure
- Handles multiple subtitle naming conventions (exact match, episode number match, etc.)
- Works with various episode numbering formats (S01E01, 01x01, [01], or standalone episode numbers like 01)
- Generates properly formatted output filenames with release tags
- Creates organized directories for output files based on show names
- Preserves existing MKV chapters and tags if no external XML files are provided
- Supports custom track naming for video and subtitles
- Detects and includes video parameters (resolution, bit depth, codec) in output filenames
- Smart subtitle resampling that skips resampling when resolutions already match

## Installation

### Requirements

- Python 3.6+
- `mkvmerge` (part of MKVToolNix)
- `ffprobe` (part of FFmpeg)
- `ass` Python library

### Installing Dependencies

#### On Debian/Ubuntu:
```bash
sudo apt-get install mkvtoolnix ffmpeg
pip install ass
```

#### On Arch Linux:
```bash
sudo pacman -S mkvtoolnix ffmpeg
pip install ass
```

#### On NixOS:
```bash
nix-env -iA nixos.mkvtoolnix nixos.ffmpeg
nix-shell -p python3Packages.ass
```

#### On macOS (using Homebrew):
```bash
brew install mkvtoolnix ffmpeg
pip install ass
```

## Usage

### Basic Usage

```bash
python mux.py
```

This will:
1. Find all MKV files in the current directory and subdirectories
2. For each MKV, look for matching subtitles, fonts, chapters, and tags
3. Resample ASS subtitles if needed to match the video resolution
4. Mux everything together into a new file with format: `[Tag] Show - E01 [Video Params].mkv`
5. Place the output files in a directory named after the show

### Command-line Arguments

```bash
python mux.py [options]
```

Available options:

| Argument | Description |
|----------|-------------|
| `--tag`, `-t` | Release tag to use in output filename (default: 'MySubs') |
| `--dir`, `-d` | Directory to search for MKV files (default: current directory) |
| `--video-track` | Custom name for video tracks (defaults to release group from filename) |
| `--sub-track` | Custom name for subtitle tracks (defaults to release group from filename) |
| `--lang`, `-l` | Force a specific subtitle language code (e.g., eng, jpn) for all subtitles |
| `--force`, `-f` | Force muxing of ALL subtitle files in the same folder as the MKV file |
| `--all-match`, `-a` | Include all subtitles that match the episode number, not just the first match |
| `--debug` | Enable debug output for troubleshooting matching issues |
| `--filenames` | Print all MKV and subtitle filenames found and exit |
| `--strict` | Use strict episode number matching (no fallback to aggressive matching) |
| `--no-resample` | Skip resampling of ASS subtitles entirely |
| `--force-resample` | Force resampling of ASS subtitles even if resolutions match |

### Examples

Process files in the current directory with custom release tag:
```bash
python mux.py --tag "MyFansub"
```

Process files in a specific directory:
```bash
python mux.py --dir "/path/to/videos"
```

Force English language for all subtitles:
```bash
python mux.py --lang eng
```

Include all matching subtitles (creates multiple output files):
```bash
python mux.py --all-match
```

Skip subtitle resampling completely:
```bash
python mux.py --no-resample
```

Use strict matching to avoid wrong subtitle matches:
```bash
python mux.py --strict
```

Troubleshooting subtitle matching issues:
```bash
python mux.py --debug --filenames
```

## Directory Structure

The script expects a directory structure like:

```
Directory/
├── Video.mkv
├── Video.ass (or Video.eng.ass)
├── fonts/
│   ├── Font1.ttf
│   ├── Font2.otf
│   └── ...
├── attachments/
│   ├── Font3.ttf
│   ├── Font4.otf
│   └── ...
├── chapters.xml (optional)
└── tags.xml (optional)
```

However, it's flexible and will work with various structures:

- Fonts can be in a `fonts/` or `attachments/` directory at the same level as the subtitle or video
- Fonts can also be directly in the same directory as the subtitle
- Subtitle files can be named after the video or based on episode numbers
- Chapters and tags can be named `[video_name].chapters.xml` or just `chapters.xml`

## Output Format

By default, the script creates output files with the following format:
```
[ReleaseTag] ShowName - E01 [1080p HEVC].mkv
```

These files are placed in subdirectories named after the show, helping organize your collection.

## Advanced Features

### Subtitle Resampling

The script automatically resamples ASS subtitles to match the video resolution, properly scaling:
- Font sizes
- Margins
- Outline and shadow thickness
- Positioning tags (\pos, \move, \org)
- Clip coordinates
- Font size override tags (\fs)

For efficiency, subtitles are only resampled when their resolution differs from the video resolution. This can be overridden with the `--no-resample` or `--force-resample` flags.

### Font Management

Fonts are only included if they're located:
- In a `fonts/` directory in the same location as the matched subtitle
- In an `attachments/` directory in the same location as the matched subtitle
- Directly in the same directory as the subtitle

This ensures that only required fonts are attached to each video.

### Intelligent Episode Matching

The script can detect episode numbers in various formats:
- S01E01 format (season and episode)
- 01x01 format (season and episode)
- [01] format (common in anime releases)
- Standalone episode numbers (01, E01, etc.)

It uses this information to match subtitles to videos even when filenames don't match exactly.

### Smart Track Naming

The script attempts to extract release group names from filenames to set appropriate track names for both video and subtitle tracks. This can be overridden with command-line options.

## Acknowledgments

This project was made possible thanks to:
- [MKVToolNix](https://mkvtoolnix.download/) for the excellent mkvmerge tool
- [FFmpeg](https://ffmpeg.org/) for ffprobe
- [ASS library](https://github.com/chireiden/ass) for Python ASS subtitle parsing
- [muxtools](https://github.com/Jaded-Encoding-Thaumaturgy/muxtools) for inspiration on proper subtitle resampling approach

## License

MIT License