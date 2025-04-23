import re
from pathlib import Path
from .constants import (
    EPISODE_PATTERNS, IGNORE_PATTERNS, SHOW_NAME_RE, 
    VIDEO_PARAMS_RE, BIT_DEPTH_RE
)

def extract_episode_info(filename):
    """
    Extract season and episode numbers from a filename.
    Returns a tuple of (season, episode) where either may be None.
    """
    for ignore_pattern in IGNORE_PATTERNS:
        matches = ignore_pattern.finditer(filename)
        skip_ranges = []
        for match in matches:
            skip_ranges.append((match.start(), match.end()))
    
    for pattern in EPISODE_PATTERNS[:2]:
        match = pattern.search(filename)
        if match:
            if not any(start <= match.start() <= end for start, end in skip_ranges):
                return (int(match.group(1)), int(match.group(2)))
    
    match = EPISODE_PATTERNS[3].search(filename)
    if match:
        if not any(start <= match.start() <= end for start, end in skip_ranges):
            return (None, int(match.group(1)))
    
    match = EPISODE_PATTERNS[4].search(filename)
    if match:
        if not any(start <= match.start() <= end for start, end in skip_ranges):
            return (None, int(match.group(1)))
    
    return (None, None)

def extract_show_name(filename):
    """
    Extract the name of the show from a filename.
    """
    episode_match = None
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            episode_match = match
            break
    
    if episode_match and episode_match.re == EPISODE_PATTERNS[3]:
        parts = re.split(r'\[\d{1,3}\]', filename, 1)
        if len(parts) > 1:
            show_part = parts[0]
            release_match = re.match(r'^\s*\[.*?\]\s*(.*?)$', show_part)
            if release_match:
                show_name = release_match.group(1).strip()
                return show_name
            return show_part.strip()
    
    match = SHOW_NAME_RE.search(filename)
    if match:
        return match.group(1).strip()
    
    clean_name = re.sub(r'\[\d{1,3}\]', '', filename)
    clean_name = re.sub(r'\[[^\]]*(?:bit|p|x\d+|HEVC|h26[45]|flac|aac)[^\]]*\]', '', clean_name, flags=re.IGNORECASE)
    
    if clean_name.startswith('['):
        rbracket = clean_name.find(']')
        if rbracket > 0:
            clean_name = clean_name[rbracket+1:].strip()
            
    return clean_name.strip()

def extract_release_group(filename):
    """
    Extract the release group name from a filename.
    """
    bracket_match = re.match(r'^\s*\[([^]]+)\]', filename)
    if bracket_match:
        return bracket_match.group(1).strip()
    
    paren_match = re.match(r'^\s*\(([^)]+)\)', filename)
    if paren_match:
        return paren_match.group(1).strip()
    
    return None

def format_episode_number(season, episode):
    """
    Format season and episode numbers into a standardized string.
    For episodes with season, use SXXEXX format.
    For standalone episodes with no season, use just the episode number XX.
    """
    if season is not None:
        return f"S{season:02d}E{episode:02d}"
    return f"{episode:02d}"

def generate_output_filename(video_path, release_tag):
    """
    Generate an output filename based on the video path and release tag.
    """
    filename = video_path.stem
    
    show_name = extract_show_name(filename)
    
    season, episode = extract_episode_info(filename)
    episode_str = ""
    if episode is not None:
        episode_str = f" - {format_episode_number(season, episode)}"
    
    from .video import get_video_params  # Import here to avoid circular imports
    video_params = get_video_params(video_path)
    params_str = f" [{' '.join(video_params)}]" if video_params else ""
    
    return f"[{release_tag}] {show_name}{episode_str}{params_str}{video_path.suffix}"

def extract_lang_from_filename(path):
    """
    Extract language code from a filename.
    Returns the language code (e.g., 'eng', 'jpn') or None if not found.
    """
    from .constants import LANG_RE
    
    if path is None:
        return None
        
    m = LANG_RE.search(path.name)
    if m:
        return m.group('lang')
    return None