"""
Core muxing engine for Muxxy.
Handles the business logic of muxing operations, separated from UI.
"""
from pathlib import Path
from typing import List, Optional, Callable, Tuple
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.video import mux_sub_and_fonts, find_chapters_file, find_tags_file
from modules.subtitles import shift_subtitle_timing, resample_ass_subtitle
from modules.fonts import find_fonts_for_episode
from modules.parsers import extract_lang_from_filename
from modules.matcher import Matcher, MatchResult


# Type for progress callbacks: (current, total, video_name) -> None
ProgressCallback = Callable[[int, int, str], None]


class MuxingEngine:
    """Core muxing engine with support for single and batch operations."""
    
    def __init__(self, config=None, debug: bool = False):
        """
        Initialize muxing engine.
        
        Args:
            config: MuxxyConfig instance (optional)
            debug: Enable debug output
        """
        self.config = config
        self.debug = debug
        self.matcher = Matcher(debug=debug)
        self._cancelled = False
    
    def cancel(self):
        """Cancel ongoing batch operation."""
        self._cancelled = True
    
    def mux_single(self, match: MatchResult, 
                  subtitle_lang: Optional[str] = None,
                  shift_frames: int = 0,
                  no_resample: bool = False,
                  force_resample: bool = False,
                  video_track_name: Optional[str] = None,
                  sub_track_name: Optional[str] = None,
                  release_tag: Optional[str] = None,
                  output_dir: Optional[Path] = None) -> bool:
        """
        Mux a single video with its subtitle.
        
        Args:
            match: MatchResult containing video and subtitle paths
            subtitle_lang: Override subtitle language
            shift_frames: Number of frames to shift subtitles
            no_resample: Skip subtitle resampling
            force_resample: Force subtitle resampling
            video_track_name: Custom video track name
            sub_track_name: Custom subtitle track name
            release_tag: Release tag for output filename
            output_dir: Output directory
            
        Returns:
            True if successful, False otherwise
        """
        if match.subtitle_path is None:
            print(f"No subtitle for {match.video_path.name}, skipping")
            return False
        
        try:
            # Process subtitle
            sub_path = match.subtitle_path
            
            # Shift timing if requested
            if shift_frames != 0:
                print(f"Shifting subtitles by {shift_frames} frames")
                sub_path = shift_subtitle_timing(sub_path, shift_frames)
            
            # Resample if needed
            sub_path = resample_ass_subtitle(
                sub_path, match.video_path,
                force_resample=force_resample,
                no_resample=no_resample
            )
            
            # Determine subtitle language
            if subtitle_lang is None:
                subtitle_lang = extract_lang_from_filename(sub_path)
            
            # Find fonts
            font_files = find_fonts_for_episode(match.video_path, sub_path)
            
            # Find chapters and tags
            chapters_file = find_chapters_file(match.video_path)
            tags_file = find_tags_file(match.video_path)
            
            # Perform muxing
            mux_sub_and_fonts(
                match.video_path,
                sub_path,
                subtitle_lang,
                font_files,
                chapters_file,
                tags_file,
                release_tag,
                video_track_name,
                sub_track_name,
                output_dir
            )
            
            return True
            
        except Exception as e:
            print(f"Error muxing {match.video_path.name}: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return False
    
    def mux_batch(self, matches: List[MatchResult],
                 progress_callback: Optional[ProgressCallback] = None,
                 max_workers: int = 4,
                 **mux_options) -> Tuple[int, int]:
        """
        Mux multiple videos with their subtitles in parallel.
        
        Args:
            matches: List of MatchResults
            progress_callback: Optional callback for progress updates
            max_workers: Maximum number of parallel workers
            **mux_options: Additional options passed to mux_single
            
        Returns:
            Tuple of (successes, failures)
        """
        self._cancelled = False
        successes = 0
        failures = 0
        total = len(matches)
        
        # Filter out matches without subtitles
        valid_matches = [m for m in matches if m.subtitle_path is not None]
        
        if not valid_matches:
            print("No valid matches to process")
            return (0, 0)
        
        print(f"\nStarting batch mux of {len(valid_matches)} files with {max_workers} workers...")
        
        def mux_worker(match: MatchResult, index: int) -> Tuple[bool, str]:
            """Worker function for parallel muxing."""
            if self._cancelled:
                return (False, match.video_path.name)
            
            success = self.mux_single(match, **mux_options)
            return (success, match.video_path.name)
        
        # Process in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_match = {
                executor.submit(mux_worker, match, i): (match, i)
                for i, match in enumerate(valid_matches)
            }
            
            # Process completed tasks
            for future in as_completed(future_to_match):
                if self._cancelled:
                    # Cancel remaining tasks
                    for f in future_to_match:
                        f.cancel()
                    break
                
                match, index = future_to_match[future]
                try:
                    success, video_name = future.result()
                    if success:
                        successes += 1
                    else:
                        failures += 1
                    
                    # Call progress callback
                    if progress_callback:
                        progress_callback(successes + failures, total, video_name)
                        
                except Exception as e:
                    print(f"Error processing {match.video_path.name}: {e}")
                    failures += 1
                    if progress_callback:
                        progress_callback(successes + failures, total, match.video_path.name)
        
        print(f"\nBatch mux complete: {successes} succeeded, {failures} failed")
        if self._cancelled:
            print("Operation was cancelled")
        
        return (successes, failures)
    
    def preview_matches(self, matches: List[MatchResult], 
                       confidence_threshold: float = 0.7) -> None:
        """
        Print a preview of matches for user review.
        
        Args:
            matches: List of MatchResults
            confidence_threshold: Threshold for highlighting low-confidence matches
        """
        print("\n" + "="*80)
        print("MATCH PREVIEW")
        print("="*80)
        
        for i, match in enumerate(matches, 1):
            print(f"\n{i}. Video: {match.video_path.name}")
            
            if match.subtitle_path:
                confidence_indicator = "✓" if match.is_confident(confidence_threshold) else "⚠"
                print(f"   {confidence_indicator} Subtitle: {match.subtitle_path.name}")
                print(f"   Confidence: {match.confidence:.0%} ({match.match_type})")
                print(f"   Reason: {match.reason}")
            else:
                print(f"   ✗ No subtitle match found")
                print(f"   Reason: {match.reason}")
        
        print("\n" + "="*80)
        
        # Summary
        matched = sum(1 for m in matches if m.subtitle_path is not None)
        high_conf = sum(1 for m in matches if m.is_confident(confidence_threshold))
        low_conf = matched - high_conf
        no_match = len(matches) - matched
        
        print(f"Total videos: {len(matches)}")
        print(f"  High confidence matches: {high_conf}")
        print(f"  Low confidence matches: {low_conf}")
        print(f"  No matches: {no_match}")
        print("="*80 + "\n")
