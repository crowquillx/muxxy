#!/usr/bin/env python3
"""
Muxxy - A tool for muxing subtitles, fonts, and other attachments into MKV files.
"""

import sys
from muxxy.cli import main as cli_main
from muxxy.tui import run_tui

if __name__ == "__main__":
    # If no arguments are provided, launch the TUI
    # Otherwise, pass arguments to the CLI as before
    if len(sys.argv) <= 1:
        run_tui()
    else:
        cli_main()