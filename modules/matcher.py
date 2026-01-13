"""
Enhanced matching engine for intelligent video-subtitle pairing.
Uses episode/season detection with fuzzy matching and confidence scoring.
"""
import re
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from thefuzz import fuzz

from modules.parsers import extract_episode_info, extract_show_name
from modules.constants import SUB_EXTS


@dataclass
class MatchResult:
    """Represents a video-subtitle match with confidence score."""
    video_path: Path
    subtitle_path: Optional[Path]
    confidence: float  # 0.0 to 1.0
    match_type: str  # 'exact', 'episode', 'fuzzy', 'manual', 'none'
    reason: str  # Human-readable explanation
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if match confidence exceeds threshold."""
        return self.confidence >= threshold


class Matcher:
    """Intelligent matching engine for video-subtitle pairing."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
    
    def find_all_subtitles(self, root: Path) -> List[Path]:
        """Find all subtitle files in directory tree."""
        all_subs = []
        for ext in SUB_EXTS:
            all_subs.extend(root.rglob(f'*{ext}'))
        return all_subs
    
    def match_single(self, video_path: Path, subtitle_candidates: List[Path],
                    strict: bool = False) -> MatchResult:
        """
        Find the best subtitle match for a single video file.
        
        Args:
            video_path: Path to the video file
            subtitle_candidates: List of potential subtitle files
            strict: If True, only return high-confidence matches
            
        Returns:
            MatchResult with best match (subtitle_path may be None if no good match)
        """
        if not subtitle_candidates:
            return MatchResult(
                video_path=video_path,
                subtitle_path=None,
                confidence=0.0,
                match_type='none',
                reason='No subtitle files found'
            )
        
        # Extract video information
        video_season, video_episode = extract_episode_info(video_path.stem)
        video_show = extract_show_name(video_path.stem)
        
        if self.debug:
            print(f"\n=== Matching for: {video_path.name} ===")
            print(f"Video show: '{video_show}'")
            print(f"Video S{video_season}E{video_episode}")
        
        best_match = None
        best_score = 0.0
        best_reason = ""
        best_type = "none"
        
        for sub_path in subtitle_candidates:
            score, match_type, reason = self._score_match(
                video_path, sub_path, video_season, video_episode, video_show
            )
            
            if self.debug:
                print(f"  {sub_path.name}: {score:.2f} ({match_type}) - {reason}")
            
            if score > best_score:
                best_score = score
                best_match = sub_path
                best_reason = reason
                best_type = match_type
        
        # Apply strict threshold if needed
        if strict and best_score < 0.9:
            return MatchResult(
                video_path=video_path,
                subtitle_path=None,
                confidence=best_score,
                match_type='none',
                reason=f'Best match below strict threshold: {best_reason}'
            )
        
        return MatchResult(
            video_path=video_path,
            subtitle_path=best_match,
            confidence=best_score,
            match_type=best_type,
            reason=best_reason
        )
    
    def _score_match(self, video_path: Path, sub_path: Path,
                    video_season: Optional[int], video_episode: Optional[int],
                    video_show: str) -> Tuple[float, str, str]:
        """
        Score a potential video-subtitle match.
        
        Returns:
            Tuple of (score, match_type, reason)
        """
        sub_season, sub_episode = extract_episode_info(sub_path.stem)
        sub_show = extract_show_name(sub_path.stem)
        
        # 1. Exact filename match (excluding extension)
        if video_path.stem == sub_path.stem:
            return (1.0, 'exact', 'Exact filename match')
        
        # 2. Same base with language code
        if sub_path.stem.startswith(video_path.stem + '.'):
            return (0.99, 'exact', 'Exact match with language code')
        
        # 3. Episode number matching
        if video_episode is not None and sub_episode is not None:
            if video_episode == sub_episode:
                # Same episode number
                episode_score = 0.6
                
                # Check if seasons match (if both have season info)
                if video_season is not None and sub_season is not None:
                    if video_season == sub_season:
                        episode_score = 0.8
                        reason = f'Episode S{video_season:02d}E{video_episode:02d} match'
                    else:
                        # Different seasons - low score
                        return (0.2, 'episode', f'Episode match but different season (S{video_season} vs S{sub_season})')
                else:
                    reason = f'Episode E{video_episode:02d} match (no season info)'
                
                # Boost score if show names are similar
                if video_show and sub_show:
                    show_similarity = self._string_similarity(video_show, sub_show)
                    if show_similarity > 0.8:
                        episode_score += 0.15
                        reason += ' with similar show name'
                    elif show_similarity > 0.5:
                        episode_score += 0.05
                
                return (min(episode_score, 0.95), 'episode', reason)
        
        # 4. Fuzzy show name matching (only if no episode info)
        if video_show and sub_show and video_episode is None:
            similarity = self._string_similarity(video_show, sub_show)
            if similarity > 0.9:
                return (0.7, 'fuzzy', f'High show name similarity ({similarity:.0%})')
            elif similarity > 0.7:
                return (0.5, 'fuzzy', f'Moderate show name similarity ({similarity:.0%})')
        
        # 5. No match
        return (0.0, 'none', 'No matching criteria')
    
    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity using fuzzy matching."""
        # Normalize strings
        norm1 = re.sub(r'[^a-zA-Z0-9]', '', str1.lower())
        norm2 = re.sub(r'[^a-zA-Z0-9]', '', str2.lower())
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use token sort ratio for better matching of reordered words
        return fuzz.token_sort_ratio(norm1, norm2) / 100.0
    
    def match_batch(self, video_files: List[Path], subtitle_files: List[Path],
                   strict: bool = False) -> List[MatchResult]:
        """
        Match multiple video files to subtitles.
        
        Args:
            video_files: List of video file paths
            subtitle_files: List of subtitle file paths
            strict: If True, only return high-confidence matches
            
        Returns:
            List of MatchResults, one per video file
        """
        results = []
        
        for video_path in video_files:
            # For each video, consider all subtitle candidates
            result = self.match_single(video_path, subtitle_files, strict)
            results.append(result)
        
        return results
    
    def get_alternative_matches(self, video_path: Path, subtitle_candidates: List[Path],
                               top_n: int = 5) -> List[Tuple[Path, float, str]]:
        """
        Get alternative subtitle matches for manual selection.
        
        Returns:
            List of (subtitle_path, confidence, reason) tuples, sorted by confidence
        """
        video_season, video_episode = extract_episode_info(video_path.stem)
        video_show = extract_show_name(video_path.stem)
        
        matches = []
        for sub_path in subtitle_candidates:
            score, match_type, reason = self._score_match(
                video_path, sub_path, video_season, video_episode, video_show
            )
            matches.append((sub_path, score, reason))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches[:top_n]
