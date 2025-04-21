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
import datetime

# Supported subtitle and font extensions
SUB_EXTS = ['.ass', '.srt', '.ssa', '.sub']
FONT_EXTS = ['.ttf', '.otf', '.ttc']
FONTS_DIR = 'fonts'
ATTACHMENTS_DIR = 'attachments'
TEMP_DIR = 'temp_mux'

DEFAULT_RELEASE_TAG = 'MySubs'

VIDEO_PARAMS_RE = re.compile(r'(\d+)p|(\d+)x(\d+)')
BIT_DEPTH_RE = re.compile(r'(8|10)bit', re.IGNORECASE)

LANG_RE = re.compile(r'\.(?P<lang>[a-z]{2,3})\.[^.]+$')

EPISODE_PATTERNS = [
    re.compile(r'S(\d+)E(\d+)', re.IGNORECASE),
    re.compile(r'(\d+)x(\d+)', re.IGNORECASE),
    re.compile(r' - (\d{1,2})(?:\s|$|\[)', re.IGNORECASE),
    re.compile(r'\[(\d{1,3})(?!\d)(?!p)(?!x\d)(?!bit)(?!-bit)\]'),
    re.compile(r'(?<![0-9])E?(\d{1,3})(?![0-9xp])', re.IGNORECASE),
]

IGNORE_PATTERNS = [
    re.compile(r'\[[^\]]*\d+x\d+[^\]]*\]'),
    re.compile(r'\[[^\]]*\d+p[^\]]*\]'),
    re.compile(r'\[[^\]]*(?:DVDRip|BDRip|WebRip)[^\]]*\]', re.IGNORECASE),
    re.compile(r'\[[^\]]*(?:x26[45]|hevc|avc|flac|ac3|mp3)[^\]]*\]', re.IGNORECASE),
]

SHOW_NAME_RE = re.compile(r'(?:\[.+?\]\s*)*(.+?)(?:\s+-\s+|\s+S\d+E\d+|\s+\d+x\d+|\s+E\d+|\s+\[\d{1,3}\]|\s+\[\d{4}\])')

def extract_episode_info(filename):
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
    bracket_match = re.match(r'^\s*\[([^]]+)\]', filename)
    if bracket_match:
        return bracket_match.group(1).strip()
    
    paren_match = re.match(r'^\s*\(([^)]+)\)', filename)
    if paren_match:
        return paren_match.group(1).strip()
    
    return None

def get_video_params(video_path):
    params = []
    
    width, height = get_video_resolution(video_path)
    if width and height:
        if height in [480, 720, 1080, 2160]:
            params.append(f"{height}p")
        else:
            params.append(f"{width}x{height}")
    
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
            params.append('10bit')
            
        encoder = stream.get('tags', {}).get('encoder', '')
        if 'x265' in encoder.lower() or 'hevc' in encoder.lower():
            params.append('HEVC')
        elif 'x264' in encoder.lower() or 'avc' in encoder.lower():
            params.append('h264')
    except Exception as e:
        print(f"Warning: Could not get video parameters: {e}")
    
    return params

def format_episode_number(season, episode):
    if season is not None:
        return f"S{season:02d}E{episode:02d}"
    return f"E{episode:02d}"

def generate_output_filename(video_path, release_tag):
    filename = video_path.stem
    
    show_name = extract_show_name(filename)
    
    season, episode = extract_episode_info(filename)
    episode_str = ""
    if episode is not None:
        episode_str = f" - {format_episode_number(season, episode)}"
    
    video_params = get_video_params(video_path)
    params_str = f" [{' '.join(video_params)}]" if video_params else ""
    
    return f"[{release_tag}] {show_name}{episode_str}{params_str}{video_path.suffix}"

def find_mkv_files(root):
    return list(root.rglob('*.mkv'))

def find_subtitle_files(root):
    all_subs = []
    for ext in SUB_EXTS:
        all_subs.extend(root.rglob(f'*{ext}'))
    return all_subs

def find_matching_subtitles(video_path, force=False, all_matches=False, debug=False):
    base = video_path.stem
    video_season, video_episode = extract_episode_info(base)
    matching_subs = []
    
    if debug:
        print(f"DEBUG: Video filename: {base}")
        print(f"DEBUG: Extracted episode info: S{video_season}, E{video_episode}")
    
    if force:
        for ext in SUB_EXTS:
            for sub in video_path.parent.glob(f"*{ext}"):
                if debug:
                    print(f"DEBUG: Force mode - including subtitle: {sub.name}")
                matching_subs.append(sub)
        return matching_subs if matching_subs else []
    
    for ext in SUB_EXTS:
        for sub in video_path.parent.glob(f"{base}.*{ext}"):
            if debug:
                print(f"DEBUG: Exact name match (with language code): {sub.name}")
            matching_subs.append(sub)
            if not all_matches:
                return matching_subs
        
        sub_path = video_path.with_suffix(ext)
        if sub_path.exists():
            if debug:
                print(f"DEBUG: Direct name match: {sub_path.name}")
            matching_subs.append(sub_path)
            if not all_matches:
                return matching_subs
    
    if video_episode is None:
        if debug:
            print(f"DEBUG: No episode number detected in video filename. Skipping episode-based matching.")
        return matching_subs
    
    video_show_name = extract_show_name(base)
    
    if debug:
        print(f"DEBUG: Looking for episode {video_episode} with show name: '{video_show_name}'")
        
    normalized_video_show = re.sub(r'[^a-zA-Z0-9]', '', video_show_name.lower())
    
    all_subs_in_dir = []
    for ext in SUB_EXTS:
        all_subs_in_dir.extend(list(video_path.parent.glob(f"*{ext}")))
    
    if debug:
        print(f"DEBUG: Found {len(all_subs_in_dir)} total subtitle files in directory")
        
    for sub_path in all_subs_in_dir:
        sub_season, sub_episode = extract_episode_info(sub_path.stem)
        
        if sub_episode is None or sub_episode != video_episode:
            if debug:
                print(f"DEBUG: Skipping {sub_path.name} - Episode mismatch: video={video_episode}, sub={sub_episode}")
            continue
            
        sub_show_name = extract_show_name(sub_path.stem)
        normalized_sub_show = re.sub(r'[^a-zA-Z0-9]', '', sub_show_name.lower())
        
        if debug:
            print(f"DEBUG: Checking subtitle: {sub_path.name}")
            print(f"DEBUG:   - Subtitle show: '{sub_show_name}'")
            print(f"DEBUG:   - Subtitle episode: S{sub_season}, E{sub_episode}")
            print(f"DEBUG:   - Episode numbers match!")
        
        similarity = 0
        if normalized_video_show and normalized_sub_show:
            if normalized_video_show in normalized_sub_show or normalized_sub_show in normalized_video_show:
                similarity = 0.9
            else:
                common_chars = set(normalized_video_show) & set(normalized_sub_show)
                max_len = max(len(normalized_video_show), len(normalized_sub_show))
                if max_len > 0:
                    similarity = len(common_chars) / max_len
        
        if debug:
            print(f"DEBUG:   - Show name similarity: {similarity:.2f}")
            
        if similarity >= 0.7 or normalized_video_show == normalized_sub_show:
            if debug:
                print(f"DEBUG:   - Show names match with sufficient similarity")
            matching_subs.append(sub_path)
            if not all_matches:
                return matching_subs
        else:
            words_video = re.findall(r'\b\w{3,}\b', video_show_name.lower())
            words_sub = re.findall(r'\b\w{3,}\b', sub_show_name.lower())
            
            matching_words = [w for w in words_video if w in words_sub]
            
            if len(matching_words) >= 2 and len(words_video) > 0 and len(words_sub) > 0:
                word_similarity = len(matching_words) / min(len(words_video), len(words_sub))
                if word_similarity >= 0.5:
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
    
    if not matching_subs and all_matches:
        if debug:
            print(f"DEBUG: Searching recursively for episode {video_episode}")
            
        for ext in SUB_EXTS:
            for sub_path in video_path.parent.rglob(f"*{ext}"):
                if sub_path in all_subs_in_dir:
                    continue
                    
                sub_season, sub_episode = extract_episode_info(sub_path.stem)
                
                if sub_episode == video_episode:
                    sub_show_name = extract_show_name(sub_path.stem)
                    similarity = 0
                    
                    if video_show_name and sub_show_name:
                        normalized_sub_show = re.sub(r'[^a-zA-Z0-9]', '', sub_show_name.lower())
                        if normalized_video_show in normalized_sub_show or normalized_sub_show in normalized_video_show:
                            similarity = 0.9
                    
                    if similarity >= 0.8:
                        if debug:
                            print(f"DEBUG: Recursive match: {sub_path.name} (similarity: {similarity:.2f})")
                        matching_subs.append(sub_path)
                        if not all_matches:
                            return matching_subs
    
    return matching_subs

def extract_lang_from_filename(path):
    if path is None:
        return None
        
    m = LANG_RE.search(path.name)
    if m:
        return m.group('lang')
    return None

def ass_timestamp_to_ms(timestamp):
    if isinstance(timestamp, datetime.timedelta):
        return int(timestamp.total_seconds() * 1000)
        
    hours, minutes, seconds_cs = timestamp.split(':')
    seconds, centiseconds = seconds_cs.split('.')
    
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
    total_ms += int(centiseconds) * 10
    
    return total_ms

def ms_to_ass_timestamp(ms):
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10
    
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def shift_subtitle_timing(sub_path, frames):
    if frames == 0:
        return sub_path
    
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    unique_id = str(uuid.uuid4())[:8]
    shifted_sub_path = temp_dir_path / f"{sub_path.stem}_shifted_{unique_id}{sub_path.suffix}"
    
    if sub_path.suffix.lower() in ['.ass', '.ssa']:
        try:
            with open(sub_path, 'r', encoding='utf-8-sig') as f:
                doc = ass.parse(f)
            
            fps = 23.976
            if hasattr(doc.info, 'Timer') and doc.info.Timer:
                try:
                    fps = float(doc.info.Timer)
                except (ValueError, TypeError):
                    pass
                    
            frame_duration_ms = 1000 / fps
            shift_ms = int(frames * frame_duration_ms)
            
            for event in doc.events:
                start_ms = ass_timestamp_to_ms(event.start)
                end_ms = ass_timestamp_to_ms(event.end)
                
                start_ms += shift_ms
                end_ms += shift_ms
                
                if start_ms < 0:
                    start_ms = 0
                if end_ms < 0:
                    end_ms = 0
                
                event.start = ms_to_ass_timestamp(start_ms)
                event.end = ms_to_ass_timestamp(end_ms)
            
            with open(shifted_sub_path, 'w', encoding='utf-8') as f:
                doc.dump_file(f)
                
            print(f"Shifted subtitle by {frames} frames ({shift_ms}ms at {fps:.3f}fps)")
            return shifted_sub_path
            
        except Exception as e:
            print(f"Error shifting ASS subtitle: {e}")
            return sub_path
            
    elif sub_path.suffix.lower() == '.srt':
        try:
            with open(sub_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s-->\s(\d{2}):(\d{2}):(\d{2}),(\d{3})')
            
            fps = 23.976
            frame_duration_ms = 1000 / fps
            shift_ms = int(frames * frame_duration_ms)
            
            def replace_timestamp(match):
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
                
                start_ms = (h1 * 3600 + m1 * 60 + s1) * 1000 + ms1
                end_ms = (h2 * 3600 + m2 * 60 + s2) * 1000 + ms2
                
                start_ms += shift_ms
                end_ms += shift_ms
                
                if start_ms < 0:
                    start_ms = 0
                if end_ms < 0:
                    end_ms = 0
                
                start_h = int(start_ms // 3600000)
                start_m = int((start_ms % 3600000) // 60000)
                start_s = int((start_ms % 60000) // 1000)
                start_ms = int(start_ms % 1000)
                
                end_h = int(end_ms // 3600000)
                end_m = int((end_ms % 3600000) // 60000)
                end_s = int((end_ms % 60000) // 1000)
                end_ms = int(end_ms % 1000)
                
                return f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
            
            shifted_content = pattern.sub(replace_timestamp, content)
            
            with open(shifted_sub_path, 'w', encoding='utf-8') as f:
                f.write(shifted_content)
                
            print(f"Shifted subtitle by {frames} frames ({shift_ms}ms at {fps:.3f}fps)")
            return shifted_sub_path
            
        except Exception as e:
            print(f"Error shifting SRT subtitle: {e}")
            return sub_path
    
    print(f"Subtitle format {sub_path.suffix} doesn't support shifting, using original")
    return sub_path

def get_font_attachments(fonts_dir):
    attachments = []
    if not fonts_dir.exists():
        return attachments
    for font_file in fonts_dir.iterdir():
        if font_file.suffix.lower() in FONT_EXTS:
            lang = extract_lang_from_filename(font_file)
            attachments.append((font_file, lang))
    return attachments

def find_fonts_for_episode(episode_path, subtitle_path=None):
    attachments = []
    
    if subtitle_path is not None:
        subtitle_dir = subtitle_path.parent
        
        sub_fonts_dir = subtitle_dir / FONTS_DIR
        sub_attachments_dir = subtitle_dir / ATTACHMENTS_DIR
        
        for dir_path in [sub_fonts_dir, sub_attachments_dir]:
            attachments.extend(get_font_attachments(dir_path))
        
        for font_ext in FONT_EXTS:
            for font_file in subtitle_dir.glob(f"*{font_ext}"):
                lang = extract_lang_from_filename(font_file)
                attachments.append((font_file, lang))
    
    if not attachments:
        local_fonts = episode_path.parent / FONTS_DIR
        local_attachments = episode_path.parent / ATTACHMENTS_DIR
        
        for dir_path in [local_fonts, local_attachments]:
            attachments.extend(get_font_attachments(dir_path))
        
        for font_ext in FONT_EXTS:
            for font_file in episode_path.parent.glob(f"*{font_ext}"):
                lang = extract_lang_from_filename(font_file)
                attachments.append((font_file, lang))
    
    return attachments

def find_chapters_file(video_path):
    video_season, video_episode = extract_episode_info(video_path.stem)
    
    chapters_file = video_path.with_name(f"{video_path.stem}.chapters.xml")
    if chapters_file.exists():
        return chapters_file
    
    if video_episode is not None:
        for chapter_path in video_path.parent.rglob("*.chapters.xml"):
            chapter_season, chapter_episode = extract_episode_info(chapter_path.stem)
            if chapter_episode == video_episode:
                if video_season is None or chapter_season is None or video_season == chapter_season:
                    return chapter_path
    
    chapters_file = video_path.parent / "chapters.xml"
    if chapters_file.exists():
        return chapters_file
    
    current_dir = video_path.parent
    for _ in range(2):
        if current_dir.parent == current_dir:
            break
        current_dir = current_dir.parent
        chapters_file = current_dir / "chapters.xml"
        if chapters_file.exists():
            return chapters_file
            
    return None
    
def find_tags_file(video_path):
    video_season, video_episode = extract_episode_info(video_path.stem)
    
    tags_file = video_path.with_name(f"{video_path.stem}.tags.xml")
    if tags_file.exists():
        return tags_file
    
    if video_episode is not None:
        for tag_path in video_path.parent.rglob("*.tags.xml"):
            tag_season, tag_episode = extract_episode_info(tag_path.stem)
            if tag_episode == video_episode:
                if video_season is None or tag_season is None or video_season == tag_season:
                    return tag_path
    
    tags_file = video_path.parent / "tags.xml"
    if tags_file.exists():
        return tags_file
    
    current_dir = video_path.parent
    for _ in range(2):
        if current_dir.parent == current_dir:
            break
        current_dir = current_dir.parent
        tags_file = current_dir / "tags.xml"
        if tags_file.exists():
            return tags_file
            
    return None

def get_video_resolution(video_path):
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
    return 23.976

def resample_ass_subtitle(sub_path, video_path, force_resample=False, no_resample=False):
    if sub_path.suffix.lower() != '.ass' or no_resample:
        return sub_path
    
    video_width, video_height = get_video_resolution(video_path)
    if video_width == 0 or video_height == 0:
        print(f"Warning: Could not get resolution for {video_path}, skipping subtitle resample")
        return sub_path
    
    try:
        with open(sub_path, 'r', encoding='utf-8-sig') as f:
            doc = ass.parse(f)
        
        script_info = doc.info
        orig_width = int(getattr(script_info, 'PlayResX', 0) or 0)
        orig_height = int(getattr(script_info, 'PlayResY', 0) or 0)
        
        if orig_width == 0:
            orig_width = 1280
        if orig_height == 0:
            orig_height = 720
        
        if not force_resample and orig_width == video_width and orig_height == video_height:
            print(f"Subtitle resolution ({orig_width}x{orig_height}) already matches video - skipping resample")
            return sub_path
        
        temp_dir_path = Path(TEMP_DIR)
        temp_dir_path.mkdir(exist_ok=True)
        
        unique_id = str(uuid.uuid4())[:8]
        resampled_sub_path = temp_dir_path / f"{sub_path.stem}_resampled_{unique_id}.ass"
        
        script_info.PlayResX = str(video_width)
        script_info.PlayResY = str(video_height)
        
        scale_x = video_width / orig_width
        scale_y = video_height / orig_height
        
        for style in doc.styles:
            style.fontsize = str(float(style.fontsize) * scale_y)
            
            style.marginl = str(int(float(style.marginl) * scale_x))
            style.marginr = str(int(float(style.marginr) * scale_x))
            style.marginv = str(int(float(style.marginv) * scale_y))
            
            style.outline = str(float(style.outline) * scale_y)
            style.shadow = str(float(style.shadow) * scale_y)
            
            if hasattr(style, 'spacing'):
                style.spacing = str(float(style.spacing) * scale_x)
        
        for event in doc.events:
            if '\\pos(' in event.text:
                event.text = re.sub(
                    r'\\pos\(([^,]+),([^)]+)\)', 
                    lambda m: f"\\pos({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y})", 
                    event.text
                )
            
            if '\\move(' in event.text:
                event.text = re.sub(
                    r'\\move\(([^,]+),([^,]+),([^,]+),([^)]+)\)',
                    lambda m: f"\\move({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y},{float(m.group(3)) * scale_x},{float(m.group(4)) * scale_y})",
                    event.text
                )
            
            if '\\org(' in event.text:
                event.text = re.sub(
                    r'\\org\(([^,]+),([^)]+)\)',
                    lambda m: f"\\org({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y})",
                    event.text
                )
            
            if '\\clip(' in event.text:
                event.text = re.sub(
                    r'\\clip\(([^,]+),([^,]+),([^,]+),([^)]+)\)',
                    lambda m: f"\\clip({float(m.group(1)) * scale_x},{float(m.group(2)) * scale_y},{float(m.group(3)) * scale_x},{float(m.group(4)) * scale_y})",
                    event.text
                )
            
            if '\\fs' in event.text:
                event.text = re.sub(
                    r'\\fs([0-9.]+)',
                    lambda m: f"\\fs{float(m.group(1)) * scale_y}",
                    event.text
                )
        
        with open(resampled_sub_path, 'w', encoding='utf-8') as f:
            doc.dump_file(f)
        
        print(f"Resampled subtitle from {orig_width}x{orig_height} to {video_width}x{video_height}")
        return resampled_sub_path
        
    except Exception as e:
        print(f"Error while resampling subtitle: {e}")
        if 'resampled_sub_path' in locals() and resampled_sub_path.exists():
            resampled_sub_path.unlink(missing_ok=True)
        return sub_path

def check_mkv_has_chapters_and_tags(video_path):
    cmd = [
        'mkvmerge', '-i', '-F', 'json', str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        has_chapters = False
        has_tags = False
        
        if 'chapters' in data and data['chapters']:
            has_chapters = True
        
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
    output_filename = generate_output_filename(video_path, release_tag)
    
    show_name = extract_show_name(video_path.stem)
    
    if output_dir:
        show_dir = Path(output_dir) / f"[{release_tag}] {show_name.strip()}"
    else:
        show_dir = video_path.parent / show_name.strip()
    
    show_dir.mkdir(exist_ok=True)
    
    output_path = show_dir / output_filename
    
    has_chapters, has_tags = False, False
    if chapters_file is None or tags_file is None:
        has_chapters, has_tags = check_mkv_has_chapters_and_tags(video_path)
    
    if video_track_name is None:
        video_track_name = extract_release_group(video_path.name)
        
    if sub_path and sub_track_name is None:
        sub_track_name = extract_release_group(sub_path.name)
    
    cmd = ['mkvmerge', '-o', str(output_path)]
    
    if not chapters_file and has_chapters:
        print("  - Using existing chapters from source file")
    else:
        cmd.append('--no-chapters')
    
    if video_track_name:
        cmd += ['--track-name', f'0:{video_track_name}']
    cmd.append(str(video_path))
    
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
    
    for font, font_lang in font_files:
        if font_lang:
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', font.name, '--attachment-description', font_lang, '--attach-file', str(font)]
        else:
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', font.name, '--attach-file', str(font)]
    
    if chapters_file:
        cmd += ['--chapters', str(chapters_file)]
    
    if tags_file:
        cmd += ['--tags', f"0:{tags_file}"]
    elif not has_tags:
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
        sys.exit(e.code)
    
    root = Path(args.directory)
    
    output_dir = args.output_dir if args.output_dir else root
    
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    try:
        mkv_files = find_mkv_files(root)
        print(f"Found {len(mkv_files)} MKV files to process")
        
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
            subtitles = find_matching_subtitles(mkv, force=args.force, all_matches=args.all_match or args.force, debug=args.debug)
            
            if not subtitles and not args.force and not args.strict:
                print(f"No subtitles found with standard matching for {mkv.name}, trying more aggressive matching...")
                
                all_subs_in_dir = []
                for ext in SUB_EXTS:
                    all_subs_in_dir.extend(list(mkv.parent.glob(f"*{ext}")))
                
                if args.debug:
                    print(f"DEBUG: Found {len(all_subs_in_dir)} subtitle files in directory")
                
                video_season, video_episode = extract_episode_info(mkv.stem)
                
                if video_episode is not None:
                    for sub_path in all_subs_in_dir:
                        sub_season, sub_episode = extract_episode_info(sub_path.stem)
                        if sub_episode == video_episode:
                            if args.debug:
                                print(f"DEBUG: Last resort match by episode number alone: {sub_path.name}")
                            subtitles.append(sub_path)
                            if not args.all_match:
                                break
            
            if not subtitles:
                print(f"No subtitles found for {mkv.name}, skipping")
                continue
            
            if args.shift_frames:
                print(f"Shifting subtitles by {args.shift_frames} frames")
                subtitles = [shift_subtitle_timing(sub, args.shift_frames) for sub in subtitles]
                
            subtitles = [resample_ass_subtitle(sub, mkv, force_resample=args.force_resample, no_resample=args.no_resample) for sub in subtitles]
            
            sub_langs = []
            for sub in subtitles:
                if args.subtitle_lang:
                    sub_langs.append(args.subtitle_lang)
                else:
                    lang = extract_lang_from_filename(sub)
                    sub_langs.append(lang)
            
            font_files = find_fonts_for_episode(mkv, subtitles[0] if subtitles else None)
            
            chapters_file = find_chapters_file(mkv)
            tags_file = find_tags_file(mkv)
            
            for sub_path, sub_lang in zip(subtitles, sub_langs):
                video_season, video_episode = extract_episode_info(mkv.stem)
                sub_season, sub_episode = extract_episode_info(sub_path.stem)
                
                if not args.force and video_episode is not None and sub_episode is not None and video_episode != sub_episode:
                    print(f"WARNING: Episode number mismatch between video ({video_episode}) and subtitle ({sub_episode}). Skipping.")
                    continue
                
                print(f"\nProcessing subtitle: {sub_path.name}")
                mux_sub_and_fonts(
                    mkv, sub_path, sub_lang, font_files, chapters_file, tags_file, 
                    args.release_tag, args.video_track_name, args.sub_track_name, output_dir
                )
    finally:
        if temp_dir_path.exists():
            for file in temp_dir_path.glob("*"):
                file.unlink(missing_ok=True)
            try:
                temp_dir_path.rmdir()
            except:
                print(f"Warning: Could not remove temporary directory {temp_dir_path}")

if __name__ == '__main__':
    main()
