import re

# Supported file extensions
SUB_EXTS = ['.ass', '.srt', '.ssa', '.sub']
FONT_EXTS = ['.ttf', '.otf', '.ttc']

# Directories
FONTS_DIR = 'fonts'
ATTACHMENTS_DIR = 'attachments'
TEMP_DIR = 'temp_mux'

# Default settings
DEFAULT_RELEASE_TAG = 'MySubs'

# Regular expressions for video, language, and episode parsing
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