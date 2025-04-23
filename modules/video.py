import json
import subprocess
from pathlib import Path

def get_video_resolution(video_path):
    """
    Get the resolution of a video file.
    Returns a tuple of (width, height).
    """
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-select_streams', 'v:0', 
        '-show_entries', 'stream=width,height', 
        '-of', 'json', 
        str(video_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data.get('streams', [{}])[0]
        width = stream.get('width', 0)
        height = stream.get('height', 0)
        return width, height
    except (IndexError, KeyError, subprocess.SubprocessError) as e:
        print(f"Warning: Could not get resolution for {video_path}: {e}")
        return 0, 0

def get_video_fps(video_path):
    """
    Get the frame rate of a video file.
    Returns a float representing frames per second.
    """
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

def get_video_params(video_path):
    """
    Get video parameters (resolution, bit depth, encoder) suitable for 
    including in a filename.
    Returns a list of string parameters.
    """
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

def find_mkv_files(root):
    """
    Find all MKV files recursively starting from root directory.
    """
    return list(root.rglob('*.mkv'))

def check_mkv_has_chapters_and_tags(video_path):
    """
    Check if an MKV file has chapters and tags.
    Returns a tuple of (has_chapters, has_tags).
    """
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

def find_chapters_file(video_path):
    """
    Find a chapters file matching the video file.
    Returns the path to a chapters file or None.
    """
    from .parsers import extract_episode_info
    
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
    """
    Find a tags file matching the video file.
    Returns the path to a tags file or None.
    """
    from .parsers import extract_episode_info
    
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

def get_mkv_tracks(video_path):
    """
    Get track information from an MKV file.
    Returns a dictionary with track information including types, codec, language, etc.
    """
    cmd = [
        'mkvmerge', '-i', '-F', 'json', str(video_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        return data.get('tracks', [])
    except Exception as e:
        print(f"Warning: Could not get track information for {video_path}: {e}")
        return []

def mux_sub_and_fonts(video_path, sub_path, sub_lang, font_files, chapters_file=None, 
                      tags_file=None, release_tag=None, video_track_name=None, 
                      sub_track_name=None, output_dir=None):
    """
    Mux subtitle and fonts with a video file into a new MKV file.
    """
    from .parsers import extract_show_name, extract_release_group, generate_output_filename
    from .constants import DEFAULT_RELEASE_TAG
    
    if release_tag is None:
        release_tag = DEFAULT_RELEASE_TAG
        
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
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', 
                   font.name, '--attachment-description', font_lang, '--attach-file', str(font)]
        else:
            cmd += ['--attachment-mime-type', 'application/x-truetype-font', '--attachment-name', 
                   font.name, '--attach-file', str(font)]
    
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

def extract_mkv_track(video_path, track_id, output_dir=None):
    """
    Extract a specific track from an MKV file.
    
    Args:
        video_path (Path): Path to the MKV file
        track_id (int): ID of the track to extract
        output_dir (Path, optional): Directory to save the extracted file. Defaults to video's directory.
    
    Returns:
        Path: Path to the extracted file, or None if extraction failed
    """
    import tempfile
    
    try:
        # Get track info to determine the appropriate file extension
        tracks = get_mkv_tracks(video_path)
        track_info = None
        
        for track in tracks:
            if track.get('id') == track_id:
                track_info = track
                break
        
        if not track_info:
            print(f"Error: Track ID {track_id} not found in {video_path}")
            return None
        
        track_type = track_info.get('type')
        track_codec = track_info.get('codec', '')
        track_properties = track_info.get('properties', {})
        track_lang = track_properties.get('language', 'und')
        track_name = track_properties.get('track_name', '')
        
        # Determine extension based on track type and codec
        extension = '.bin'  # Default
        if track_type == 'video':
            if 'h264' in track_codec.lower() or 'avc' in track_codec.lower():
                extension = '.h264'
            elif 'hevc' in track_codec.lower() or 'h265' in track_codec.lower():
                extension = '.h265'
            else:
                extension = '.mkv'
        elif track_type == 'audio':
            if 'aac' in track_codec.lower():
                extension = '.aac'
            elif 'ac3' in track_codec.lower():
                extension = '.ac3'
            elif 'dts' in track_codec.lower():
                extension = '.dts'
            elif 'flac' in track_codec.lower():
                extension = '.flac'
            else:
                extension = '.mka'
        elif track_type == 'subtitles':
            if 'ass' in track_codec.lower() or 'ssa' in track_codec.lower():
                extension = '.ass'
            elif 'srt' in track_codec.lower() or 'subrip' in track_codec.lower():
                extension = '.srt'
            else:
                extension = '.sup'
        
        # Create output filename
        output_dir = Path(output_dir) if output_dir else video_path.parent
        output_dir.mkdir(exist_ok=True)
        
        filename_base = f"{video_path.stem}_track{track_id}_{track_type}"
        if track_lang and track_lang != 'und':
            filename_base += f".{track_lang}"
        
        output_path = output_dir / f"{filename_base}{extension}"
        
        # Extract the track
        cmd = [
            'mkvextract', 'tracks', str(video_path),
            f"{track_id}:{str(output_path)}"
        ]
        
        print(f"Extracting track {track_id} from {video_path.name}...")
        print(f"  - Track type: {track_type}")
        print(f"  - Codec: {track_codec}")
        if track_lang and track_lang != 'und':
            print(f"  - Language: {track_lang}")
        if track_name:
            print(f"  - Track name: {track_name}")
        print(f"  - Output: {output_path}")
        
        subprocess.run(cmd, check=True)
        
        return output_path
    except Exception as e:
        print(f"Error extracting track {track_id} from {video_path}: {e}")
        return None

def mux_selected_tracks(output_path, track_sources):
    """
    Mux selected tracks into a new MKV file.
    
    Args:
        output_path (Path): Path for the output MKV file
        track_sources (list): List of tuples containing:
            (source_file (Path), track_id (int), track_type (str), 
             language (str, optional), track_name (str, optional))
    
    Returns:
        bool: True if muxing was successful, False otherwise
    """
    try:
        cmd = ['mkvmerge', '-o', str(output_path)]
        
        # Process each track source
        for i, (source_file, track_id, track_type, language, track_name) in enumerate(track_sources):
            track_options = []
            
            # Add track-specific options
            if language:
                track_options.extend(['--language', f'{track_id}:{language}'])
            
            if track_name:
                track_options.extend(['--track-name', f'{track_id}:{track_name}'])
            
            # Handle special case for first file
            if i == 0:
                if track_options:
                    cmd.extend(track_options)
                cmd.append(str(source_file))
            else:
                # For subsequent files, we need to specify the file with its options
                if track_options:
                    cmd.extend(track_options)
                cmd.append(str(source_file))
        
        print(f"Muxing tracks into {output_path}...")
        print(f"Command: {' '.join(cmd)}")
        
        subprocess.run(cmd, check=True)
        print(f"Successfully created: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error during muxing: {e}")
        return False