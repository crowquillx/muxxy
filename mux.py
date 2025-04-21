import os
import subprocess
import json
import tempfile
from pathlib import Path
import re
import shutil
import uuid
import ass
import argparse
import sys
import datetime  # Add datetime module for timestamp handling

# Supported subtitle and font extensions
SUB_EXTS = ['.ass', '.srt', '.ssa', '.sub']
FONT_EXTS = ['.ttf', '.otf', '.ttc']
FONTS_DIR = 'fonts'
ATTACHMENTS_DIR = 'attachments'
TEMP_DIR = 'temp_mux'

# Default release tag - can be overridden via command line eg python mux.py --tag "YourReleaseGroup"
DEFAULT_RELEASE_TAG = 'MySubs'

# Video parameters for naming
VIDEO_PARAMS_RE = re.compile(r'(\d+)p|(\d+)x(\d+)')
BIT_DEPTH_RE = re.compile(r'(8|10)bit', re.IGNORECASE)

LANG_RE = re.compile(r'\.(?P<lang>[a-z]{2,3})\.[^.]+$')

# Episode pattern matching
EPISODE_PATTERNS = [
    re.compile(r'S(\d+)E(\d+)', re.IGNORECASE),      # S01E01 format
    re.compile(r'(\d+)x(\d+)', re.IGNORECASE),       # 01x01 format
    re.compile(r' - (\d{1,2})(?:\s|$|\[)', re.IGNORECASE),   # Name - 01 format common for anime
    re.compile(r'\[(\d{1,3})(?!\d)(?!p)(?!x\d)(?!bit)(?!-bit)\]'),   # [01] format common in anime
    re.compile(r'(?<![0-9])E?(\d{1,3})(?![0-9xp])', re.IGNORECASE),   # E01 or 01 format (standalone)
]

# Patterns to explicitly ignore for episode detection (technical specs, resolutions, etc.)
IGNORE_PATTERNS = [
    re.compile(r'\[[^\]]*\d+x\d+[^\]]*\]'),          # Any brackets containing resolution like [960x720]
    re.compile(r'\[[^\]]*\d+p[^\]]*\]'),             # Any brackets containing resolution like [1080p]
    re.compile(r'\[[^\]]*(?:DVDRip|BDRip|WebRip)[^\]]*\]', re.IGNORECASE),  # Source indicators
    re.compile(r'\[[^\]]*(?:x26[45]|hevc|avc|flac|ac3|mp3)[^\]]*\]', re.IGNORECASE),  # Codec indicators
]

# Show name pattern
SHOW_NAME_RE = re.compile(r'(?:\[.+?\]\s*)*(.+?)(?:\s+-\s+|\s+S\d+E\d+|\s+\d+x\d+|\s+E\d+|\s+\[\d{1,3}\]|\s+\[\d{4}\])')

def extract_episode_info(filename):
    """
    Extract season and episode numbers from filename.
    Returns tuple (season, episode) or (None, episode) or (None, None)
    """
    # First check if the pattern might be a technical spec that we should ignore
    for ignore_pattern in IGNORE_PATTERNS:
        # For any potential match we find in brackets that could be a resolution or spec, mark it to skip
        matches = ignore_pattern.finditer(filename)
        skip_ranges = []
        for match in matches:
            skip_ranges.append((match.start(), match.end()))
    
    # Check for season and episode patterns
    for pattern in EPISODE_PATTERNS[:2]:  # First two patterns have both season and episode
        match = pattern.search(filename)
        if match:
            # Make sure it's not inside a range we want to skip
            if not any(start <= match.start() <= end for start, end in skip_ranges):
                return (int(match.group(1)), int(match.group(2)))
    
    # Check for bracketed episode number [01] format
    match = EPISODE_PATTERNS[3].search(filename)
    if match:
        # Make sure it's not inside a range we want to skip
        if not any(start <= match.start() <= end for start, end in skip_ranges):
            return (None, int(match.group(1)))
    
    # Check for standalone episode number
    match = EPISODE_PATTERNS[4].search(filename)
    if match:
        # Make sure it's not inside a range we want to skip
        if not any(start <= match.start() <= end for start, end in skip_ranges):
            return (None, int(match.group(1)))
    
    return (None, None)

def extract_show_name(filename):
    """Extract show name from filename"""
    # First, try to find and extract the episode number
    episode_match = None
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            episode_match = match
            break
    
    # Handle anime-style release names with brackets
    if episode_match and episode_match.re == EPISODE_PATTERNS[3]:  # If it's the [01] format
        # Find the show name between the first bracket group and the episode number bracket
        parts = re.split(r'\[\d{1,3}\]', filename, 1)
        if len(parts) > 1:
            show_part = parts[0]
            # If show part has a release group in brackets, extract the actual show name
            release_match = re.match(r'^\s*\[.*?\]\s*(.*?)$', show_part)
            if release_match:
                show_name = release_match.group(1).strip()
                return show_name
            return show_part.strip()
    
    # Try the regular pattern match 
    match = SHOW_NAME_RE.search(filename)
    if match:
        return match.group(1).strip()
    
    # If all else fails, clean up the name
    clean_name = re.sub(r'\[\d{1,3}\]', '', filename)
    clean_name = re.sub(r'\[[^\]]*(?:bit|p|x\d+|HEVC|h26[45]|flac|aac)[^\]]*\]', '', clean_name, flags=re.IGNORECASE)
    
    # Remove any remaining brackets at the start (likely release group)
    if clean_name.startswith('['):
        rbracket = clean_name.find(']')
        if rbracket > 0:
            clean_name = clean_name[rbracket+1:].strip()
            
    return clean_name.strip()

def extract_release_group(filename):
    """Extract the release group name from a filename, typically in square brackets"""
    # Common pattern: [Group] or [Group1&Group2]
    bracket_match = re.match(r'^\s*\[([^]]+)\]', filename)
    if bracket_match:
        return bracket_match.group(1).strip()
    
    # Some files have release group name in parentheses
    paren_match = re.match(r'^\s*\(([^)]+)\)', filename)
    if paren_match:
        return paren_match.group(1).strip()
    
    return None

def get_video_params(video_path):
    """Get video parameters (resolution, bit depth, codec) using ffprobe"""
    params = []
    
    # Get resolution
    width, height = get_video_resolution(video_path)
    if width and height:
        if height in [480, 720, 1080, 2160]:
            params.append(f"{height}p")
        else:
            params.append(f"{width}x{height}")
    
    # Get bit depth
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=bits_per_raw_sample:stream_tags=encoder',
        '-of', 'json',
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        stream = data.get('streams', [{}])[0]
        bit_depth = stream.get('bits_per_raw_sample', '')
        
        if bit_depth and bit_depth != '8':
            params.append(f"{bit_depth}bit")
        elif '10bit' in video_path.name.lower() or '10 bit' in video_path.name.lower():
            # Fallback to checking filename
            params.append('10bit')
            
        # Get encoder/codec info
        encoder = stream.get('tags', {}).get('encoder', '')
        if 'x265' in encoder.lower() or 'hevc' in encoder.lower():
            params.append('HEVC')
        elif 'x264' in encoder.lower() or 'avc' in encoder.lower():
            params.append('h264')
    except Exception as e:
        print(f"Warning: Could not get video parameters: {e}")
    
    return params

def format_episode_number(season, episode):
    """Format episode number as 'SxxExx' or 'Exx'"""
    if season is not None:
        return f"S{season:02d}E{episode:02d}"
    return f"E{episode:02d}"

def generate_output_filename(video_path, release_tag):
    """Generate output filename in the format: [tag] Name - EXX [Video Params].ext"""
    filename = video_path.stem
    
    # Extract show name
    show_name = extract_show_name(filename)
    
    # Extract season and episode
    season, episode = extract_episode_info(filename)
    episode_str = ""
    if episode is not None:
        episode_str = f" - {format_episode_number(season, episode)}"
    
    # Get video parameters
    video_params = get_video_params(video_path)
    params_str = f" [{' '.join(video_params)}]" if video_params else ""
    
    # Build output filename
    return f"[{release_tag}] {show_name}{episode_str}{params_str}{video_path.suffix}"

def find_mkv_files(root):
    """Recursively find all mkv files"""
    return list(root.rglob('*.mkv'))

def find_subtitle_files(root):
    """Recursively find all subtitle files"""
    all_subs = []
    for ext in SUB_EXTS:
        all_subs.extend(root.rglob(f'*{ext}'))
    return all_subs

def find_matching_subtitles(video_path, force=False, all_matches=False, debug=False):
    """
    Find subtitle files that match the video based on episode number or name
    Returns a list of matching subtitle files
    
    Parameters:
    - video_path: Path to the video file
    - force: If True, returns all subtitle files in the same folder as the video
    - all_matches: If True, returns all subtitle files that match the episode number
    - debug: If True, print debug information about matching process
    """
    base = video_path.stem
    video_season, video_episode = extract_episode_info(base)
    matching_subs = []
    
    # Debug info
    if debug:
        print(f"DEBUG: Video filename: {base}")
        print(f"DEBUG: Extracted episode info: S{video_season}, E{video_episode}")
    
    # If force flag is set, return all subtitle files in the same folder
    if force:
        for ext in SUB_EXTS:
            for sub in video_path.parent.glob(f"*{ext}"):
                if debug:
                    print(f"DEBUG: Force mode - including subtitle: {sub.name}")
                matching_subs.append(sub)
        return matching_subs if matching_subs else []
    
    # Try exact name matching first
    for ext in SUB_EXTS:
        # Check for language code in subtitle filename
        for sub in video_path.parent.glob(f"{base}.*{ext}"):
            if debug:
                print(f"DEBUG: Exact name match (with language code): {sub.name}")
            matching_subs.append(sub)
            if not all_matches:
                return matching_subs
        
        # Try direct name match
        sub_path = video_path.with_suffix(ext)
        if sub_path.exists():
            if debug:
                print(f"DEBUG: Direct name match: {sub_path.name}")
            matching_subs.append(sub_path)
            if not all_matches:
                return matching_subs
    
    # If we don't have episode info for the video, we can't do episode-based matching
    if video_episode is None:
        if debug:
            print(f"DEBUG: No episode number detected in video filename. Skipping episode-based matching.")
        return matching_subs
    
    # Extract the base anime title (without release groups and other info)
    video_show_name = extract_show_name(base)
    
    if debug:
        print(f"DEBUG: Looking for episode {video_episode} with show name: '{video_show_name}'")
        
    # Create a normalized version of the show name for loose matching
    normalized_video_show = re.sub(r'[^a-zA-Z0-9]', '', video_show_name.lower())
    
    # Get all subtitle files in the same directory
    all_subs_in_dir = []
    for ext in SUB_EXTS:
        all_subs_in_dir.extend(list(video_path.parent.glob(f"*{ext}")))
    
    if debug:
        print(f"DEBUG: Found {len(all_subs_in_dir)} total subtitle files in directory")
        
    # Process each subtitle file
    for sub_path in all_subs_in_dir:
        sub_season, sub_episode = extract_episode_info(sub_path.stem)
        
        # Skip if subtitle doesn't have an episode number or if it doesn't match the video episode
        if sub_episode is None or sub_episode != video_episode:
            if debug:
                print(f"DEBUG: Skipping {sub_path.name} - Episode mismatch: video={video_episode}, sub={sub_episode}")
            continue
            
        # Extract and compare show names
        sub_show_name = extract_show_name(sub_path.stem)
        normalized_sub_show = re.sub(r'[^a-zA-Z0-9]', '', sub_show_name.lower())
        
        if debug:
            print(f"DEBUG: Checking subtitle: {sub_path.name}")
            print(f"DEBUG:   - Subtitle show: '{sub_show_name}'")
            print(f"DEBUG:   - Subtitle episode: S{sub_season}, E{sub_episode}")
            print(f"DEBUG:   - Episode numbers match!")
        
        # Calculate string similarity between normalized show names
        similarity = 0
        if normalized_video_show and normalized_sub_show:
            # Calculate simple string containment
            if normalized_video_show in normalized_sub_show or normalized_sub_show in normalized_video_show:
                similarity = 0.9  # High similarity if one contains the other
            else:
                # Calculate character overlap
                common_chars = set(normalized_video_show) & set(normalized_sub_show)
                max_len = max(len(normalized_video_show), len(normalized_sub_show))
                if max_len > 0:
                    similarity = len(common_chars) / max_len
        
        if debug:
            print(f"DEBUG:   - Show name similarity: {similarity:.2f}")
            
        # Check if show names are similar enough (adjust threshold as needed)
        if similarity >= 0.7 or normalized_video_show == normalized_sub_show:
            if debug:
                print(f"DEBUG:   - Show names match with sufficient similarity")
            matching_subs.append(sub_path)
            if not all_matches:
                return matching_subs
        else:
            # Special case: Check for direct substring matches in titles
            words_video = re.findall(r'\b\w{3,}\b', video_show_name.lower())
            words_sub = re.findall(r'\b\w{3,}\b', sub_show_name.lower())
            
            # Count matching words
            matching_words = [w for w in words_video if w in words_sub]
            
            if len(matching_words) >= 2 and len(words_video) > 0 and len(words_sub) > 0:
                word_similarity = len(matching_words) / min(len(words_video), len(words_sub))
                if word_similarity >= 0.5:  # At least half the words match
                    if debug:
                        print(f"DEBUG:   - Word match with similarity {word_similarity:.2f}")
                        print(f"DEBUG:   - Matching words: {matching_words}")
                    matching_subs.append(sub_path)
                    if not all_matches:
                        return matching_subs
                else:
                    if debug:
                        print(f"DEBUG:   - Word match insufficient: {word_similarity:.2f}")
            else:
                if debug:
                    print(f"DEBUG:   - Not enough matching words: {matching_words}")
    
    # If still no match and we explicitly want to search recursively, look in subdirectories
    # This is intentionally limited to avoid accidental matches from different series
    if not matching_subs and all_matches:
        if debug:
            print(f"DEBUG: Searching recursively for episode {video_episode}")
            
        # Search recursively from video's parent directory
        for ext in SUB_EXTS:
            for sub_path in video_path.parent.rglob(f"*{ext}"):
                # Skip files we already checked
                if sub_path in all_subs_in_dir:
                    continue
                    
                sub_season, sub_episode = extract_episode_info(sub_path.stem)
                
                # Check for exact episode match
                if sub_episode == video_episode:
                    # Extra check: make sure it's the same series by comparing show names
                    sub_show_name = extract_show_name(sub_path.stem)
                    similarity = 0
                    
                    # Only calculate similarity if both show names are available
                    if video_show_name and sub_show_name:
                        normalized_sub_show = re.sub(r'[^a-zA-Z0-9]', '', sub_show_name.lower())
                        if normalized_video_show in normalized_sub_show or normalized_sub_show in normalized_video_show:
                            similarity = 0.9
                    
                    # Only include if show names are very similar
                    if similarity >= 0.8:
                        if debug:
                            print(f"DEBUG: Recursive match: {sub_path.name} (similarity: {similarity:.2f})")
                        matching_subs.append(sub_path)
                        if not all_matches:
                            return matching_subs
    
    return matching_subs

def extract_lang_from_filename(path):
    """Extract language code from filename"""
    if path is None:
        return None
        
    m = LANG_RE.search(path.name)
    if m:
        return m.group('lang')
    return None

def ass_timestamp_to_ms(timestamp):
    """Convert ASS timestamp (h:mm:ss.cc) to milliseconds"""
    # Handle if timestamp is already a timedelta object
    if isinstance(timestamp, datetime.timedelta):
        return int(timestamp.total_seconds() * 1000)
        
    # ASS format: h:mm:ss.cc (centiseconds)
    hours, minutes, seconds_cs = timestamp.split(':')
    seconds, centiseconds = seconds_cs.split('.')
    
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
    total_ms += int(centiseconds) * 10  # Convert centiseconds to milliseconds
    
    return total_ms

def ms_to_ass_timestamp(ms):
    """Convert milliseconds to ASS timestamp format (h:mm:ss.cc)"""
    # Calculate components
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10  # Convert to centiseconds (hundredths of a second)
    
    # Format as h:mm:ss.cc
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def shift_subtitle_timing(sub_path, frames):
    """
    Shift subtitle timing by a specified number of frames
    
    Parameters:
    - sub_path: Path to the subtitle file
    - frames: Number of frames to shift (positive = delay, negative = advance)
    
    Returns path to the shifted subtitle file
    """
    if frames == 0:
        return sub_path  # No shifting needed
    
    # Create temp directory if it doesn't exist
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    # Generate unique filename for the shifted subtitle
    unique_id = str(uuid.uuid4())[:8]
    shifted_sub_path = temp_dir_path / f"{sub_path.stem}_shifted_{unique_id}{sub_path.suffix}"
    
    # Handle different subtitle formats
    if sub_path.suffix.lower() in ['.ass', '.ssa']:
        try:
            # Use ass library for ASS/SSA files with direct frame shifting
            with open(sub_path, 'r', encoding='utf-8-sig') as f:
                doc = ass.parse(f)
            
            # Get video fps - first try from the subtitle's ScriptInfo section
            fps = 23.976  # Default value
            if hasattr(doc.info, 'Timer') and doc.info.Timer:
                try:
                    fps = float(doc.info.Timer)
                except (ValueError, TypeError):
                    pass
                    
            # Get frame duration in milliseconds
            frame_duration_ms = 1000 / fps
            shift_ms = int(frames * frame_duration_ms)
            
            # Shift all dialogue events by the specified number of frames
            for event in doc.events:
                # Get current timestamps in milliseconds using our own function
                start_ms = ass_timestamp_to_ms(event.start)
                end_ms = ass_timestamp_to_ms(event.end)
                
                # Apply shift by frames (converted to ms)
                start_ms += shift_ms
                end_ms += shift_ms
                
                # Ensure times don't go negative
                if start_ms < 0:
                    start_ms = 0
                if end_ms < 0:
                    end_ms = 0
                
                # Convert back to ASS timestamp format using our own function
                event.start = ms_to_ass_timestamp(start_ms)
                event.end = ms_to_ass_timestamp(end_ms)
            
            # Write shifted subtitle
            with open(shifted_sub_path, 'w', encoding='utf-8') as f:
                doc.dump_file(f)
                
            print(f"Shifted subtitle by {frames} frames ({shift_ms}ms at {fps:.3f}fps)")
            return shifted_sub_path
            
        except Exception as e:
            print(f"Error shifting ASS subtitle: {e}")
            return sub_path
            
    elif sub_path.suffix.lower() == '.srt':
        try:
            # For SRT files, use regex-based approach with frame-based shifting
            with open(sub_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # SRT timestamp format: 00:00:00,000 --> 00:00:00,000
            pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s-->\s(\d{2}):(\d{2}):(\d{2}),(\d{3})')
            
            # Standard framerate for SRT files
            fps = 23.976
            frame_duration_ms = 1000 / fps
            shift_ms = int(frames * frame_duration_ms)
            
            def replace_timestamp(match):
                # Convert timestamp to milliseconds
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
                
                # Calculate total milliseconds
                start_ms = (h1 * 3600 + m1 * 60 + s1) * 1000 + ms1
                end_ms = (h2 * 3600 + m2 * 60 + s2) * 1000 + ms2
                
                # Apply frame-based shift
                start_ms += shift_ms
                end_ms += shift_ms
                
                # Ensure times don't go negative
                if start_ms < 0:
                    start_ms = 0
                if end_ms < 0:
                    end_ms = 0
                
                # Convert back to timestamp format
                start_h = int(start_ms // 3600000)
                start_m = int((start_ms % 3600000) // 60000)
                start_s = int((start_ms % 60000) // 1000)
                start_ms = int(start_ms % 1000)
                
                end_h = int(end_ms // 3600000)
                end_m = int((end_ms % 3600000) // 60000)
                end_s = int((end_ms % 60000) // 1000)
                end_ms = int(end_ms % 1000)
                
                return f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
            
            # Apply the replacement
            shifted_content = pattern.sub(replace_timestamp, content)
            
            # Write shifted subtitle
            with open(shifted_sub_path, 'w', encoding='utf-8') as f:
                f.write(shifted_content)
                
            print(f"Shifted subtitle by {frames} frames ({shift_ms}ms at {fps:.3f}fps)")
            return shifted_sub_path
            
        except Exception as e:
            print(f"Error shifting SRT subtitle: {e}")
            return sub_path
    
    # For other formats, just return the original file
    print(f"Subtitle format {sub_path.suffix} doesn't support shifting, using original")
    return sub_path

def get_font_attachments(fonts_dir):
    """Get font attachments from a directory"""
    attachments = []
    if not fonts_dir.exists():
        return attachments
    for font_file in fonts_dir.iterdir():
        if font_file.suffix.lower() in FONT_EXTS:
            lang = extract_lang_from_filename(font_file)
            attachments.append((font_file, lang))
    return attachments

def find_fonts_for_episode(episode_path, subtitle_path=None):
    """Find fonts for the episode, prioritizing fonts in the same directory as the subtitle"""
    attachments = []
    
    # If subtitle exists, prioritize fonts from subtitle's directory
    if subtitle_path is not None:
        subtitle_dir = subtitle_path.parent
        
        # Check for fonts directory and attachments directory in subtitle folder
        sub_fonts_dir = subtitle_dir / FONTS_DIR
        sub_attachments_dir = subtitle_dir / ATTACHMENTS_DIR
        
        # Only use fonts from these directories
        for dir_path in [sub_fonts_dir, sub_attachments_dir]:
            attachments.extend(get_font_attachments(dir_path))
        
        # Also check for font files directly in the subtitle directory
        for font_ext in FONT_EXTS:
            for font_file in subtitle_dir.glob(f"*{font_ext}"):
                lang = extract_lang_from_filename(font_file)
                attachments.append((font_file, lang))
    
    # If no subtitle-specific fonts found, look in episode directory
    if not attachments:
        # Check directories in this order: episode/fonts, episode/attachments
        local_fonts = episode_path.parent / FONTS_DIR
        local_attachments = episode_path.parent / ATTACHMENTS_DIR
        
        for dir_path in [local_fonts, local_attachments]:
            attachments.extend(get_font_attachments(dir_path))
        
        # Check for font files directly in the video directory
        for font_ext in FONT_EXTS:
            for font_file in episode_path.parent.glob(f"*{font_ext}"):
                lang = extract_lang_from_filename(font_file)
                attachments.append((font_file, lang))
    
    return attachments

def find_chapters_file(video_path):
    """Look for chapters.xml file with matching episode number or in the same directory"""
    video_season, video_episode = extract_episode_info(video_path.stem)
    
    # First check for exact name match
    chapters_file = video_path.with_name(f"{video_path.stem}.chapters.xml")
    if chapters_file.exists():
        return chapters_file
    
    # If we have episode info, search recursively for matching episode chapters
    if video_episode is not None:
        for chapter_path in video_path.parent.rglob("*.chapters.xml"):
            chapter_season, chapter_episode = extract_episode_info(chapter_path.stem)
            if chapter_episode == video_episode:
                if video_season is None or chapter_season is None or video_season == chapter_season:
                    return chapter_path
    
    # Check for generic chapters.xml in same directory or parent directories
    # First check video's directory
    chapters_file = video_path.parent / "chapters.xml"
    if chapters_file.exists():
        return chapters_file
    
    # Then check parent directories up to 2 levels
    current_dir = video_path.parent
    for _ in range(2):  # Check up to 2 parent directories
        if current_dir.parent == current_dir:  # Reached root
            break
        current_dir = current_dir.parent
        chapters_file = current_dir / "chapters.xml"
        if chapters_file.exists():
            return chapters_file
            
    return None
    
def find_tags_file(video_path):
    """Look for tags.xml file with matching episode number or in the same directory"""
    video_season, video_episode = extract_episode_info(video_path.stem)
    
    # First check for exact name match
    tags_file = video_path.with_name(f"{video_path.stem}.tags.xml")
    if tags_file.exists():
        return tags_file
    
    # If we have episode info, search recursively for matching episode tags
    if video_episode is not None:
        for tag_path in video_path.parent.rglob("*.tags.xml"):
            tag_season, tag_episode = extract_episode_info(tag_path.stem)
            if tag_episode == video_episode:
                if video_season is None or tag_season is None or video_season == tag_season:
                    return tag_path
    
    # Check for generic tags.xml in same directory or parent directories
    # First check video's directory
    tags_file = video_path.parent / "tags.xml"
    if tags_file.exists():
        return tags_file
    
    # Then check parent directories up to 2 levels
    current_dir = video_path.parent
    for _ in range(2):  # Check up to 2 parent directories
        if current_dir.parent == current_dir:  # Reached root
            break
        current_dir = current_dir.parent
        tags_file = current_dir / "tags.xml"
        if tags_file.exists():
            return tags_file
            
    return None

def get_video_resolution(video_path):
    """Get video width and height using ffprobe"""
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-select_streams', 'v:0', 
        '-show_entries', 'stream=width,height', 
        '-of', 'json', 
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    try:
        stream = data.get('streams', [{}])[0]
        width = stream.get('width', 0)
        height = stream.get('height', 0)
        return width, height
    except (IndexError, KeyError):
        print(f"Warning: Could not get resolution for {video_path}")
        return 0, 0

def get_video_fps(video_path):
    """Get video FPS using ffprobe"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'csv=p=0',
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fps = result.stdout.strip()
        if fps:
            num, denom = map(int, fps.split('/'))
            return num / denom
    except Exception as e:
        print(f"Warning: Could not get FPS for {video_path}: {e}")
    return 23.976  # Default fallback

def resample_ass_subtitle(sub_path, video_path, force_resample=False, no_resample=False):
    """
    Resample ASS subtitle to match video resolution using the ass library.
    This provides proper resampling of all elements including positioning.
    
    Parameters:
    - sub_path: Path to the subtitle file
    - video_path: Path to the video file
    - force_resample: If True, resample even if resolutions are the same
    - no_resample: If True, skip resampling entirely
    """
    # Skip non-ASS subtitles or if resampling is disabled
    if sub_path.suffix.lower() != '.ass' or no_resample:
        return sub_path
    
    # Get video resolution
    video_width, video_height = get_video_resolution(video_path)
    if video_width == 0 or video_height == 0:
        print(f"Warning: Could not get resolution for {video_path}, skipping subtitle resample")
        return sub_path
    
    try:
        # Read ASS file to check its resolution
        with open(sub_path, 'r', encoding='utf-8-sig') as f:
            doc = ass.parse(f)
        
        # Get original script resolution
        script_info = doc.info
        orig_width = int(getattr(script_info, 'PlayResX', 0) or 0)
        orig_height = int(getattr(script_info, 'PlayResY', 0) or 0)
        
        # If original resolution not specified, use some defaults
        if orig_width == 0:
            orig_width = 1280  # Common default
        if orig_height == 0:
            orig_height = 720  # Common default
        
        # Skip resampling if resolutions already match (unless forced)
        if not force_resample and orig_width == video_width and orig_height == video_height:
            print(f"Subtitle resolution ({orig_width}x{orig_height}) already matches video - skipping resample")
            return sub_path
        
        # Create temp directory in current working dir if it doesn't exist
        temp_dir_path = Path(TEMP_DIR)
        temp_dir_path.mkdir(exist_ok=True)
        
        # Generate a unique filename for the resampled subtitle
        unique_id = str(uuid.uuid4())[:8]
        resampled_sub_path = temp_dir_path / f"{sub_path.stem}_resampled_{unique_id}.ass"
        
        # Set new resolution
        script_info.PlayResX = str(video_width)
        script_info.PlayResY = str(video_height)
        
        # Calculate scale factors
        scale_x = video_width / orig_width
        scale_y = video_height / orig_height
        
        # Resize all relevant style attributes
        for style in doc.styles:
            # Font size
            style.fontsize = str(float(style.fontsize) * scale_y)
            
            # Margins
            style.marginl = str(int(float(style.marginl) * scale_x))
            style.marginr = str(int(float(style.marginr) * scale_x))
            style.marginv = str(int(float(style.marginv) * scale_y))
            
            # Outline and shadow
            style.outline = str(float(style.outline) * scale_y)
            style.shadow = str(float(style.shadow) * scale_y)
            
            # Spacing
            if hasattr(style, 'spacing'):
                style.spacing = str(float(style.spacing) * scale_x)
        
        # Scale override tags in events (common positioning tags)
        for event in doc.events:
            # Process positioning tags like \pos, \move, \org, etc.
            if '\\pos(' in event.text:
                event.text = re.sub(
                    r'\\pos\(([^,]+),([^)]+)\)', 
                    lambda m: f"\\pos({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y})", 
                    event.text
                )
            
            # Process \move tags
            if '\\move(' in event.text:
                event.text = re.sub(
                    r'\\move\(([^,]+),([^,]+),([^,]+),([^)]+)\)',
                    lambda m: f"\\move({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y},{float(m.group(3)) * scale_x},{float(m.group(4)) * scale_y})",
                    event.text
                )
            
            # Process \org tags
            if '\\org(' in event.text:
                event.text = re.sub(
                    r'\\org\(([^,]+),([^)]+)\)',
                    lambda m: f"\\org({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y})",
                    event.text
                )
            
            # Process \clip tags - rectangular clips
            if '\\clip(' in event.text:
                event.text = re.sub(
                    r'\\clip\(([^,]+),([^,]+),([^,]+),([^)]+)\)',
                    lambda m: f"\\clip({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y},{float(m.group(3)) * scale_x},{float(m.group(4)) * scale_y})",
                    event.text
                )
            
            # Scale font size overrides \fs
            if '\\fs' in event.text:
                event.text = re.sub(
                    r'\\fs([0-9.]+)',
                    lambda m: f"\\fs{float(m.group(1)) * scale_y}",
                    event.text
                )
        
        # Write the resampled subtitle
        with open(resampled_sub_path, 'w', encoding='utf-8') as f:
            doc.dump_file(f)
        
        print(f"Resampled subtitle from {orig_width}x{orig_height} to {video_width}x{video_height}")
        return resampled_sub_path
        
    except Exception as e:
        print(f"Error while resampling subtitle: {e}")
        # If resampling fails, return original subtitle
        if 'resampled_sub_path' in locals() and resampled_sub_path.exists():
            resampled_sub_path.unlink(missing_ok=True)
        return sub_path

def check_mkv_has_chapters_and_tags(video_path):
    """Check if an MKV file has chapters and/or tags using mkvmerge identify"""
    cmd = [
        'mkvmerge', '-i', '-F', 'json', str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        has_chapters = False
        has_tags = False
        
        # Check if file has chapters
        if 'chapters' in data and data['chapters']:
            has_chapters = True
        
        # Check for tags (tag elements can be present in various tracks)
        tracks = data.get('tracks', [])
        for track in tracks:
            if 'properties' in track and 'tag_artist' in track['properties']:
                has_tags = True
                break
        
        return has_chapters, has_tags
    except Exception as e:
        print(f"Warning: Could not check chapters/tags in {video_path}: {e}")
        return False, False

def mux_sub_and_fonts(video_path, sub_path, sub_lang, font_files, chapters_file=None, tags_file=None, release_tag=DEFAULT_RELEASE_TAG, video_track_name=None, sub_track_name=None, output_dir=None):
    """Mux subtitles, fonts, chapters, and tags into MKV files"""
    # Generate output filename according to the requested format
    output_filename = generate_output_filename(video_path, release_tag)
    
    # Extract show name for creating a directory
    show_name = extract_show_name(video_path.stem)
    
    # Determine the output directory - create a single folder for the show
    if output_dir:
        # If output_dir is specified, create one folder for the entire show
        show_dir = Path(output_dir) / f"[{release_tag}] {show_name.strip()}"
    else:
        # Default behavior - use the video's parent directory as base
        show_dir = video_path.parent / show_name.strip()
    
    # Create the output directory if it doesn't exist
    show_dir.mkdir(exist_ok=True)
    
    # Set output path to the output directory
    output_path = show_dir / output_filename
    
    # Check if the source MKV has chapters/tags we want to preserve
    has_chapters, has_tags = False, False
    if chapters_file is None or tags_file is None:
        has_chapters, has_tags = check_mkv_has_chapters_and_tags(video_path)
    
    # Extract release group names if track names aren't specified
    if video_track_name is None:
        video_track_name = extract_release_group(video_path.name)
        
    if sub_path and sub_track_name is None:
        sub_track_name = extract_release_group(sub_path.name)
    
    # Base command
    cmd = ['mkvmerge', '-o', str(output_path)]
    
    # Keep chapters and tags from the source file if they exist and we don't have external ones
    if not chapters_file and has_chapters:
        print("  - Using existing chapters from source file")
    else:
        # Skip chapters from the source file
        cmd.append('--no-chapters')
    
    # Add the video file with track name if available
    if video_track_name:
        cmd += ['--track-name', f'0:{video_track_name}']
    cmd.append(str(video_path))
    
    # Add subtitle if available
    if sub_path:
        subtitle_options = []
        if sub_lang:
            subtitle_options += ['--language', f'0:{sub_lang}']
        if sub_track_name:
            subtitle_options += ['--track-name', f'0:{sub_track_name}']
        
        if subtitle_options:
            cmd += subtitle_options + [str(sub_path)]
        else:
            cmd.append(str(sub_path))
    
    # Add font attachments
    for font, font_lang in font_files:
        if font_lang:
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', font.name, '--attachment-description', font_lang, '--attach-file', str(font)]
        else:
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', font.name, '--attach-file', str(font)]
    
    # Add external chapters file if available
    if chapters_file:
        cmd += ['--chapters', str(chapters_file)]
    
    # Add external tags file if available or use existing tags
    if tags_file:
        cmd += ['--tags', f"0:{tags_file}"]
    elif not has_tags:
        # Only explicitly disable tags if the source doesn't have them
        # This ensures we keep existing tags when no external tags file is provided
        cmd += ['--no-global-tags']
    
    print(f"Muxing: {video_path.name}")
    print(f"  - Subtitle: {sub_path.name if sub_path else 'None'} (lang: {sub_lang})")
    if sub_path and sub_track_name:
        print(f"  - Subtitle track name: {sub_track_name}")
    print(f"  - Video track name: {video_track_name if video_track_name else 'Default'}")
    print(f"  - Fonts: {len(font_files)}")
    print(f"  - Chapters: {'External' if chapters_file else ('Keeping from source' if has_chapters else 'None')}")
    print(f"  - Tags: {'External' if tags_file else ('Keeping from source' if has_tags else 'None')}")
    print(f"  - Output directory: {show_dir}")
    print(f"  - Output filename: {output_filename}")
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully created: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error during muxing: {e}")

def main():
    """Main function to parse arguments and process MKV files"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Mux subtitles, fonts, chapters, and tags into MKV files')
    parser.add_argument('--tag', '-t', dest='release_tag', default=DEFAULT_RELEASE_TAG,
                        help=f'Release tag to use in output filename (default: {DEFAULT_RELEASE_TAG})')
    parser.add_argument('--dir', '-d', dest='directory', default='.',
                        help='Directory to search for MKV files (default: current directory)')
    parser.add_argument('--video-track', dest='video_track_name',
                        help='Custom name for video tracks (defaults to release group from filename)')
    parser.add_argument('--sub-track', dest='sub_track_name',
                        help='Custom name for subtitle tracks (defaults to release group from filename)')
    parser.add_argument('--lang', '-l', dest='subtitle_lang', 
                        help='Force a specific subtitle language code (e.g., eng, jpn) for all subtitles')
    parser.add_argument('--shift-frames', type=int, dest='shift_frames',
                        help='Shift subtitles by the specified number of frames (positive = delay, negative = advance)')
    parser.add_argument('--force', '-f', action='store_true', 
                        help='Force muxing of ALL subtitle files in the same folder as the MKV file')
    parser.add_argument('--all-match', '-a', action='store_true',
                        help='Include all subtitles that match the episode number, not just the first match')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output for troubleshooting matching issues')
    parser.add_argument('--filenames', action='store_true',
                        help='Print all MKV and subtitle filenames found and exit')
    parser.add_argument('--strict', action='store_true',
                        help='Use strict episode number matching (no fallback to aggressive matching)')
    parser.add_argument('--no-resample', action='store_true',
                        help='Skip resampling of ASS subtitles entirely')
    parser.add_argument('--force-resample', action='store_true',
                        help='Force resampling of ASS subtitles even if resolutions match')
    parser.add_argument('--output-dir', dest='output_dir',
                        help='Specify an output directory for the muxed files')
    
    try:
        args = parser.parse_args()
    except SystemExit as e:
        # Check for common issues like missing spaces between arguments
        cmd_line = ' '.join(sys.argv[1:])
        if '--lang' in cmd_line and not re.search(r'\s--lang\s', ' ' + cmd_line + ' '):
            print("\nERROR: There appears to be a missing space before --lang argument.")
            print("Correct usage example: --sub-track \"KOTEX\" --lang \"eng\"")
        elif '--sub-track' in cmd_line and not re.search(r'\s--sub-track\s', ' ' + cmd_line + ' '):
            print("\nERROR: There appears to be a missing space before --sub-track argument.")
            print("Correct usage example: --video-track \"Group\" --sub-track \"Team\"")
        elif '--video-track' in cmd_line and not re.search(r'\s--video-track\s', ' ' + cmd_line + ' '):
            print("\nERROR: There appears to be a missing space before --video-track argument.")
            print("Correct usage example: --tag \"Name\" --video-track \"Group\"")
        # Re-raise the exception to show the original error
        sys.exit(e.code)
    
    # Use the provided directory as root
    root = Path(args.directory)
    
    # Set the output directory - by default use the input directory if --output-dir is not specified
    output_dir = args.output_dir if args.output_dir else root
    
    # Create temp dir if it doesn't exist
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    try:
        mkv_files = find_mkv_files(root)
        print(f"Found {len(mkv_files)} MKV files to process")
        
        # If filenames flag is set, print all found files and exit
        if args.filenames:
            print("\nMKV files found:")
            for mkv in mkv_files:
                video_season, video_episode = extract_episode_info(mkv.stem)
                print(f"  {mkv.name} (Episode: {video_episode})")
            
            print("\nSubtitle files found:")
            all_subs = []
            for ext in SUB_EXTS:
                all_subs.extend(list(root.glob(f"**/*{ext}")))
            for sub in all_subs:
                sub_season, sub_episode = extract_episode_info(sub.stem)
                print(f"  {sub.name} (Episode: {sub_episode})")
            return
            
        for mkv in mkv_files:
            # Find subtitles - either all matching subs or forced subs
            subtitles = find_matching_subtitles(mkv, force=args.force, all_matches=args.all_match or args.force, debug=args.debug)
            
            # If no subtitles found and we're not in strict mode, try more aggressive matching as a last resort
            if not subtitles and not args.force and not args.strict:
                print(f"No subtitles found with standard matching for {mkv.name}, trying more aggressive matching...")
                
                # Get all subtitles in the same directory
                all_subs_in_dir = []
                for ext in SUB_EXTS:
                    all_subs_in_dir.extend(list(mkv.parent.glob(f"*{ext}")))
                
                if args.debug:
                    print(f"DEBUG: Found {len(all_subs_in_dir)} subtitle files in directory")
                
                # Extract episode number from video
                video_season, video_episode = extract_episode_info(mkv.stem)
                
                if video_episode is not None:
                    # Try to find any subtitle with a matching episode number ONLY
                    # This is still safe as we only match on episode number
                    for sub_path in all_subs_in_dir:
                        sub_season, sub_episode = extract_episode_info(sub_path.stem)
                        if sub_episode == video_episode:
                            if args.debug:
                                print(f"DEBUG: Last resort match by episode number alone: {sub_path.name}")
                            subtitles.append(sub_path)
                            if not args.all_match:
                                break
            
            # If no subtitles found, skip this MKV
            if not subtitles:
                print(f"No subtitles found for {mkv.name}, skipping")
                continue
            
            # Shift subtitle timing if requested
            if args.shift_frames:
                print(f"Shifting subtitles by {args.shift_frames} frames")
                subtitles = [shift_subtitle_timing(sub, args.shift_frames) for sub in subtitles]
                
            # Resample all ASS subtitles to match video resolution
            subtitles = [resample_ass_subtitle(sub, mkv, force_resample=args.force_resample, no_resample=args.no_resample) for sub in subtitles]
            
            # Determine subtitle language - use command line arg if provided, otherwise try to extract from filename
            sub_langs = []
            for sub in subtitles:
                if args.subtitle_lang:
                    sub_langs.append(args.subtitle_lang)
                else:
                    lang = extract_lang_from_filename(sub)
                    sub_langs.append(lang)
            
            # Find fonts - only use fonts from the same directory as the first subtitle
            font_files = find_fonts_for_episode(mkv, subtitles[0] if subtitles else None)
            
            # Find chapters and tags
            chapters_file = find_chapters_file(mkv)
            tags_file = find_tags_file(mkv)
            
            # Process each subtitle
            for sub_path, sub_lang in zip(subtitles, sub_langs):
                # Double check episode numbers before muxing
                video_season, video_episode = extract_episode_info(mkv.stem)
                sub_season, sub_episode = extract_episode_info(sub_path.stem)
                
                # Skip if episode numbers don't match (additional safety check)
                if not args.force and video_episode is not None and sub_episode is not None and video_episode != sub_episode:
                    print(f"WARNING: Episode number mismatch between video ({video_episode}) and subtitle ({sub_episode}). Skipping.")
                    continue
                
                print(f"\nProcessing subtitle: {sub_path.name}")
                mux_sub_and_fonts(
                    mkv, sub_path, sub_lang, font_files, chapters_file, tags_file, 
                    args.release_tag, args.video_track_name, args.sub_track_name, output_dir
                )
    finally:
        # Clean up temporary directory after processing all files
        if temp_dir_path.exists():
            for file in temp_dir_path.glob("*"):
                file.unlink(missing_ok=True)
            try:
                temp_dir_path.rmdir()
            except:
                print(f"Warning: Could not remove temporary directory {temp_dir_path}")

if __name__ == '__main__':
    main()
