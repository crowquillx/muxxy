"""
Configuration management for Muxxy.
Handles loading/saving user preferences and default settings.
"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Default configuration file location
CONFIG_DIR = Path.home() / ".config" / "muxxy"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class MuxxyConfig:
    """Application configuration settings."""
    
    # Default settings
    release_tag: str = "MySubs"
    default_directory: str = "."
    output_directory: Optional[str] = None
    
    # Matching settings
    confidence_threshold: float = 0.7  # Minimum confidence for auto-matching
    strict_matching: bool = False
    
    # Processing options
    no_resample: bool = False
    force_resample: bool = False
    shift_frames: int = 0
    
    # Track naming
    video_track_name: Optional[str] = None
    sub_track_name: Optional[str] = None
    subtitle_lang: Optional[str] = None
    
    # GUI settings
    window_width: int = 1200
    window_height: int = 800
    last_directory: Optional[str] = None
    theme: str = "system"  # system, light, dark
    
    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        if path is None:
            path = CONFIG_FILE
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'MuxxyConfig':
        """Load configuration from file, or return defaults if file doesn't exist."""
        if path is None:
            path = CONFIG_FILE
        
        if not path.exists():
            return cls()
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            return cls(**data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Could not load config from {path}: {e}")
            print("Using default configuration.")
            return cls()
    
    def update(self, **kwargs) -> None:
        """Update configuration values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
