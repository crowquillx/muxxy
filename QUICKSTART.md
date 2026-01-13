# Quick Start Guide

## Installation

```bash
# Install UV (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd muxxy
uv sync
```

## Running Muxxy

### GUI Mode (Default)
```bash
uv run python main.py
```

### CLI Mode
```bash
# Basic usage
uv run python main.py --tag "MyGroup" --dir /path/to/videos

# Preview matches first (recommended)
uv run python main.py --preview

# Batch mode with 8 workers
uv run python main.py --batch --workers 8
```

## Common Workflows

### GUI Workflow
1. Launch: `uv run python main.py`
2. Open directory with videos and subtitles
3. Select videos in left panel
4. Click "Match Files"
5. Review matches (fix any via dropdown)
6. Click "Start Muxing"

### CLI Workflow  
```bash
# 1. Preview matches
uv run python main.py --preview --dir /path/to/videos

# 2. If satisfied, run the mux
uv run python main.py --batch --tag "MySubs" --dir /path/to/videos
```

## Troubleshooting

### Command not found: uv
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal
```

### Module not found errors
```bash
# Ensure dependencies are installed
uv sync

# Always use 'uv run' prefix
uv run python main.py
```

### No matches found
- Check filenames have episode numbers
- Use `--debug` to see matching details
- Lower confidence: `--confidence-threshold 0.5`
- Use GUI for manual override

## Key Features

- **Smart Matching**: Matches by episode number, not filename
- **Manual Override**: Fix any incorrect matches in GUI
- **Batch Processing**: Process multiple files in parallel
- **Confidence Scores**: Know which matches are reliable
- **Preview Mode**: Check matches before muxing

For full documentation, see [README.md](README.md) and [AGENTS.md](AGENTS.md).
