import argparse
import sys
import re
from pathlib import Path
import shutil

from .constants import DEFAULT_RELEASE_TAG, TEMP_DIR, SUB_EXTS
from .parsers import extract_episode_info
from .video import find_mkv_files
from .matcher import Matcher, MatchResult
from core.engine import MuxingEngine
from core.config import MuxxyConfig

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
    parser.add_argument('--shift-frames', type=int, dest='shift_frames', default=0,
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
    parser.add_argument('--preview', action='store_true',
                        help='Preview matches without executing muxing')
    parser.add_argument('--confidence-threshold', type=float, dest='confidence_threshold', default=0.7,
                        help='Minimum confidence score for auto-matching (0.0-1.0, default: 0.7)')
    parser.add_argument('--batch', action='store_true',
                        help='Enable parallel batch processing')
    parser.add_argument('--workers', type=int, dest='max_workers', default=4,
                        help='Number of parallel workers for batch mode (default: 4)')
    
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
        print(f"  {mkv.name} (S{video_season:02d}E{video_episode:02d})" if video_season and video_episode else f"  {mkv.name}")
    
    print("\nSubtitle files found:")
    all_subs = []
    for ext in SUB_EXTS:
        all_subs.extend(list(root.glob(f"**/*{ext}")))
    for sub in all_subs:
        sub_season, sub_episode = extract_episode_info(sub.stem)
        print(f"  {sub.name} (S{sub_season:02d}E{sub_episode:02d})" if sub_season and sub_episode else f"  {sub.name}")

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
    Main entry point for the CLI application.
    """
    args = parse_arguments()
    root = Path(args.directory)
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    temp_dir_path = Path(TEMP_DIR)
    temp_dir_path.mkdir(exist_ok=True)
    
    try:
        # Initialize matcher and engine
        matcher = Matcher(debug=args.debug)
        engine = MuxingEngine(debug=args.debug)
        
        # Find video and subtitle files
        mkv_files = find_mkv_files(root)
        print(f"Found {len(mkv_files)} MKV files to process")
        
        if args.filenames:
            print_filenames(root)
            return
        
        if not mkv_files:
            print("No MKV files found in directory")
            return
        
        # Find all subtitle files
        subtitle_files = matcher.find_all_subtitles(root)
        print(f"Found {len(subtitle_files)} subtitle files")
        
        if not subtitle_files:
            print("No subtitle files found in directory")
            return
        
        # Perform matching
        print("\nMatching videos to subtitles...")
        matches = matcher.match_batch(mkv_files, subtitle_files, strict=args.strict)
        
        # Filter by confidence threshold
        if not args.force:
            low_confidence = [m for m in matches if m.subtitle_path and not m.is_confident(args.confidence_threshold)]
            if low_confidence:
                print(f"\nWarning: {len(low_confidence)} match(es) below confidence threshold ({args.confidence_threshold})")
                for match in low_confidence:
                    print(f"  {match.video_path.name} -> {match.subtitle_path.name} ({match.confidence:.0%})")
                print("These will be skipped. Use --confidence-threshold to adjust or --force to include all.")
            
            # Filter out low confidence matches
            matches = [
                MatchResult(
                    video_path=m.video_path,
                    subtitle_path=m.subtitle_path if m.is_confident(args.confidence_threshold) else None,
                    confidence=m.confidence,
                    match_type=m.match_type,
                    reason=m.reason
                )
                for m in matches
            ]
        
        # Preview mode
        if args.preview:
            engine.preview_matches(matches, args.confidence_threshold)
            return
        
        # Prepare mux options
        mux_options = {
            'subtitle_lang': args.subtitle_lang,
            'shift_frames': args.shift_frames,
            'no_resample': args.no_resample,
            'force_resample': args.force_resample,
            'video_track_name': args.video_track_name,
            'sub_track_name': args.sub_track_name,
            'release_tag': args.release_tag,
            'output_dir': output_dir,
        }
        
        # Execute muxing
        if args.batch:
            # Batch mode with parallel processing
            def progress_callback(current, total, filename):
                print(f"[{current}/{total}] Processed: {filename}")
            
            successes, failures = engine.mux_batch(
                matches,
                progress_callback=progress_callback,
                max_workers=args.max_workers,
                **mux_options
            )
        else:
            # Sequential mode (original behavior)
            successes = 0
            failures = 0
            
            for match in matches:
                if match.subtitle_path is None:
                    print(f"\nNo subtitle for {match.video_path.name}, skipping")
                    failures += 1
                    continue
                
                if engine.mux_single(match, **mux_options):
                    successes += 1
                else:
                    failures += 1
            
            print(f"\nComplete: {successes} succeeded, {failures} failed")
            
    finally:
        cleanup_temp_files()