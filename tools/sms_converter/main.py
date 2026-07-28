"""
Entry point for SMS Media Converter.
"""
import sys
import os

# Ensure package directory is in sys.path
pkg_dir = os.path.dirname(os.path.abspath(__file__))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

import crash_log
from app import run_app

if __name__ == "__main__":
    # Installed before anything else can throw. The shipped builds are --windowed, so
    # without this an unhandled exception closes the process with no message, no log and
    # nothing on screen -- which is exactly how the Windows 7 "app closes when I hit
    # convert" report reached us, with no way to act on it. See crash_log.py.
    crash_log.install()
    run_app()
