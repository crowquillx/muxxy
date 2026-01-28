from pathlib import Path
from .constants import FONT_EXTS, FONTS_DIR, ATTACHMENTS_DIR
from .parsers import extract_lang_from_filename

def get_font_attachments(fonts_dir):
    """
    Get all font files from a directory.
    Returns a list of tuples (font_path, language_code).
    """
    attachments = []
    font_dir_path = Path(fonts_dir)
    if not font_dir_path.exists():
        return attachments
    
    for font_file in font_dir_path.iterdir():
        if font_file.suffix.lower() in FONT_EXTS:
            lang = extract_lang_from_filename(font_file)
            attachments.append((font_file, lang))
    return attachments

def find_fonts_for_episode(episode_path, subtitle_path=None):
    """
    Find font files that should be included with an episode.
    Returns a list of tuples (font_path, language_code).
    """
    attachments = []
    
    if subtitle_path is not None:
        subtitle_dir = subtitle_path.parent
        
        sub_fonts_dir = subtitle_dir / FONTS_DIR
        sub_attachments_dir = subtitle_dir / ATTACHMENTS_DIR
        
        # Check parent directory for fonts/attachments (e.g. ../fonts)
        parent_fonts_dir = subtitle_dir.parent / FONTS_DIR
        parent_attachments_dir = subtitle_dir.parent / ATTACHMENTS_DIR
        
        for dir_path in [sub_fonts_dir, sub_attachments_dir, parent_fonts_dir, parent_attachments_dir]:
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