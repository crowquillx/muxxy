# Muxxy Project Rules

## Overview

Muxxy is a GUI/CLI application for muxing subtitles, fonts, and attachments into MKV files. The application uses PyQt6 for the GUI, with intelligent fuzzy matching for episode/season detection.

## Architecture

### Module Structure

```
muxxy/
├── main.py                    # Entry point (GUI by default, CLI with args)
├── modules/                   # Core business logic
│   ├── cli.py                 # CLI interface
│   ├── matcher.py             # Intelligent matching engine
│   ├── parsers.py             # Filename parsing utilities
│   ├── subtitles.py           # Subtitle processing
│   ├── fonts.py               # Font detection
│   ├── video.py               # Video/MKV operations
│   └── constants.py           # Shared constants
├── core/                      # Business logic layer
│   ├── config.py              # Configuration management
│   └── engine.py              # Muxing engine
└── gui/                       # Qt GUI components
    ├── app.py                 # GUI entry point
    ├── main_window.py         # Main application window
    ├── file_browser.py        # File selection widget
    ├── match_preview.py       # Match preview/override widget
    └── settings_dialog.py     # Settings dialog
```

### Key Components

1. **Matcher (`modules/matcher.py`)**: Intelligent episode matching using fuzzy string matching with confidence scoring
2. **Engine (`core/engine.py`)**: Core muxing operations with batch processing support
3. **GUI (`gui/`)**: PyQt6-based interface with manual override support
4. **CLI (`modules/cli.py`)**: Command-line interface with enhanced features

## Development Setup

### Installation with UV

This project uses [UV](https://github.com/astral-sh/uv) for dependency management:

```bash
# Install dependencies
uv pip install -e .

# Or sync all dependencies
uv sync
```

### Running the Application

```bash
# GUI mode (default)
python main.py

# CLI mode (with arguments)
python main.py --tag "MyGroup" --dir /path/to/videos
```

## Code Style Guidelines

### Python Style
- Follow PEP 8 conventions
- Use type hints where appropriate
- Document complex functions with docstrings
- Keep functions focused and single-purpose

### Module Organization
- **`modules/`**: Lower-level utilities and parsers
- **`core/`**: Business logic without UI dependencies
- **`gui/`**: Qt-specific GUI code only

### Naming Conventions
- Classes: `PascalCase` (e.g., `MatchResult`, `MuxingEngine`)
- Functions/methods: `snake_case` (e.g., `match_single`, `find_fonts`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_RELEASE_TAG`)

## Key Features

### Episode Matching
- Fuzzy matching by episode/season number (not exact filenames)
- Confidence scoring (0.0-1.0)
- Support for various naming schemes:
  - Standard: `S01E05`, `1x05`
  - Fansub: `[05]`, `- 05`
  - Absolute: `E123`

### Batch Processing
- Parallel processing with configurable workers
- Progress tracking and cancellation support
- Manual match override via GUI

### Configuration
- Stored in `~/.config/muxxy/config.json`
- Managed by `MuxxyConfig` dataclass
- Persists window size, preferences, last directory

## External Dependencies

- **mkvmerge** (MKVToolNix): Required for muxing
- **ffprobe** (FFmpeg): Required for video info extraction
- **PyQt6**: GUI framework
- **thefuzz**: Fuzzy string matching
- **ass**: ASS subtitle parsing

## Testing

Episode matching can be tested with:
```bash
python main.py --filenames --dir /path/to/test/files
python main.py --preview --dir /path/to/test/files
```

## Common Tasks

### Adding New Match Patterns
Edit `modules/constants.py` → `EPISODE_PATTERNS`

### Adjusting Match Scoring
Edit `modules/matcher.py` → `Matcher._score_match()`

### Adding GUI Features
Create widgets in `gui/` and integrate in `main_window.py`

### Modifying Output Filenames
Edit `modules/parsers.py` → `generate_output_filename()`

## Troubleshooting

### Import Errors
Ensure you're running from the project root and UV dependencies are installed:
```bash
cd /path/to/muxxy
uv sync
python main.py
```

### Qt Issues
If GUI doesn't launch, check PyQt6 installation:
```bash
uv pip install --force-reinstall PyQt6
```

### Match Quality Issues
Enable debug mode to see matching details:
```bash
python main.py --debug --preview
```
