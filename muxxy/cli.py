import argparse
import sys
from pathlib import Path
import shutil

from .constants import DEFAULT_RELEASE_TAG, TEMP_DIR, SUB_EXTS
from .parsers import extract_episode_info
from .video import (
    find_mkv_files, find_chapters_file, find_tags_file, mux_sub_and_fonts
)
from .subtitles import (
    find_matching_subtitles, shift_subtitle_timing, resample_ass_subtitle
)
from .fonts import find_fonts_for_episode

def parse_arguments():
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
    
    return args

def print_filenames(root):
    """
    Print all MKV files and subtitle files found and exit.
    """
    mkv_files = find_mkv_files(root)
    print(f"\nMKV files found:")
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

def cleanup_temp_files():
    """
    Clean up temporary files.
    """
    temp_dir_path = Path(TEMP_DIR)
    if temp_dir_path.exists():
        for file in temp_dir_path.glob("*"):
            file.unlink(missing_ok=True)
        try:
            temp_dir_path.rmdir()
        except:
            print(f"Warning: Could not remove temporary directory {temp_dir_path}")

def main():
    """
    Main entry point for the application.
    """
    import re  # Import re here to avoid circular imports with parsers
    
    args = parse_arguments()
    root = Path(args.directory)
    
    output_dir = args.output_dir if args.output_dir else root
    
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    try:
        mkv_files = find_mkv_files(root)
        print(f"Found {len(mkv_files)} MKV files to process")
        
        if args.filenames:
            print_filenames(root)
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
        cleanup_temp_files()