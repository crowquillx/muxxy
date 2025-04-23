# Muxxy Project Guide for GitHub Copilot

## Project Overview

Muxxy is a Python-based tool for automating the process of muxing (combining) subtitle files, fonts, chapters, and tags into MKV video files. It helps users who work with anime or other videos that need custom subtitles by handling the technical aspects of merging these elements.

## Project Structure

The project is organized in a modular structure with clear separation of concerns:

```
muxxy/
├── __init__.py
├── cli.py          # Command-line interface functionality
├── constants.py    # Shared constants and regex patterns
├── fonts.py        # Font file handling and discovery
├── parsers.py      # Filename parsing and metadata extraction
├── subtitles.py    # Subtitle processing (shifting, resampling)
├── tui.py          # Terminal user interface (textual-based)
└── video.py        # Video file operations and muxing

main.py             # Entry point that decides between CLI and TUI
```

## Key Components

1. **CLI Interface**: Handles command-line arguments and orchestrates the muxing process.
2. **TUI Interface**: A text-based UI built with the Textual library for interactive usage.
3. **Subtitle Processing**:
   - Matching subtitles to video files based on filename patterns and episode numbers
   - Resampling ASS subtitles to match video resolution
   - Shifting subtitle timing by frames
4. **Font Management**: Finding and attaching fonts from various locations
5. **External Files**: Support for chapters and tags in XML format

## Core Workflows

1. **File Discovery**: Finding MKV files and matching subtitle files
2. **Subtitle Matching**: Smart matching of subtitles to videos using multiple strategies
3. **Font Discovery**: Finding relevant font files for each subtitle
4. **Preprocessing**: Resampling subtitles and shifting timing if needed
5. **Muxing**: Combining everything into a final MKV file using mkvmerge

## Dependencies

- External tools: `mkvmerge` (MKVToolNix), `ffprobe` (FFmpeg)
- Python libraries: `ass` for subtitle manipulation, `textual` for TUI

## Important Design Details

1. The project is transitioning from a single script (`mux.py`) to a modular package structure (`muxxy/` directory).
2. It offers both a command-line interface and an interactive text-based UI.
3. The tool is designed to handle various anime naming conventions and directory structures.
4. Subtitle processing includes intelligent matching algorithms that can handle different naming patterns.
5. The program creates temporary files for processing subtitles and cleans them up afterward.
6. Output files are organized by show name and follow a standardized naming convention.

## Code Standards

When contributing to this project:

1. Follow the existing modular architecture
2. Keep processing functions pure when possible
3. Add appropriate error handling
4. Maintain backward compatibility with existing command-line options
5. Add docstrings and type hints to new functions
6. Keep the TUI and CLI functionality in sync

## Feature Areas

The main functionality areas where you might need to modify code:

1. **File Detection**: `video.py` and `subtitles.py` for finding files
2. **Parsing Logic**: `parsers.py` for filename parsing and metadata extraction
3. **Subtitle Processing**: `subtitles.py` for timing shifts and resampling
4. **Font Handling**: `fonts.py` for font discovery and attachment
5. **User Interface**: `tui.py` for interactive interface, `cli.py` for command-line options
6. **Muxing Process**: `video.py` contains the core muxing function

Remember that the project is actively transitioning from the single-file approach to the modular structure, so some functionality may exist in both places during this transition period.

## Common Tasks

### Adding a New Command Line Option

1. Add the option to `parse_arguments()` in `muxxy/cli.py`
2. Update the TUI option in `muxxy/tui.py` if applicable
3. Implement the actual functionality in the appropriate module
4. Update the README.md with documentation for the new option

### Adding Support for a New Subtitle Format

1. Add the extension to `SUB_EXTS` in `constants.py`
2. Update the `shift_subtitle_timing()` function in `subtitles.py` to handle the new format
3. Update any relevant processing functions that need format-specific logic

### Implementing a New Matching Algorithm

1. Add the new matching logic to `find_matching_subtitles()` in `subtitles.py`
2. Make sure it properly respects existing options like `--strict` and `--force`
3. Add appropriate debug output with the `debug` flag

### Working with External Tools

When calling external tools like `mkvmerge` or `ffprobe`, always:
1. Use subprocess with proper error handling
2. Parse JSON output when available
3. Provide helpful error messages when external tools fail