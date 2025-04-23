import re
import uuid
import ass
import datetime
from pathlib import Path
import tempfile
from .constants import SUB_EXTS, LANG_RE, TEMP_DIR
from .parsers import extract_episode_info, extract_show_name, extract_lang_from_filename

def find_subtitle_files(root):
    """
    Find all subtitle files recursively starting from root directory.
    """
    all_subs = []
    for ext in SUB_EXTS:
        all_subs.extend(root.rglob(f'*{ext}'))
    return all_subs

def find_matching_subtitles(video_path, force=False, all_matches=False, debug=False):
    """
    Find subtitle files that match the given video file.
    """
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

def ass_timestamp_to_ms(timestamp):
    """
    Convert an ASS timestamp to milliseconds.
    """
    if isinstance(timestamp, datetime.timedelta):
        return int(timestamp.total_seconds() * 1000)
        
    hours, minutes, seconds_cs = timestamp.split(':')
    seconds, centiseconds = seconds_cs.split('.')
    
    total_ms = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
    total_ms += int(centiseconds) * 10
    
    return total_ms

def ms_to_ass_timestamp(ms):
    """
    Convert milliseconds to an ASS timestamp.
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10
    
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

def shift_subtitle_timing(sub_path, frames):
    """
    Shift subtitle timing by a number of frames.
    Returns the path of the shifted subtitle file.
    """
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

def resample_ass_subtitle(sub_path, video_path, force_resample=False, no_resample=False):
    """
    Resample an ASS subtitle file to match the video resolution.
    Returns the path of the resampled subtitle file.
    """
    if sub_path.suffix.lower() != '.ass' or no_resample:
        return sub_path
    
    from .video import get_video_resolution
    
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