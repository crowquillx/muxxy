#!/usr/bin/env python3
"""
Muxxy - A tool for muxing subtitles, fonts, and other attachments into MKV files.
Entry point that launches GUI by default, or CLI when arguments are provided.
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # CLI mode - has arguments
        from modules.cli import main as cli_main
        cli_main()
    else:
        # GUI mode - no arguments
        from gui.app import run_gui
        run_gui()