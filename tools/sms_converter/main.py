"""
Entry point for SMS Media Converter.
"""
import sys
import os

# Ensure package directory is in sys.path
pkg_dir = os.path.dirname(os.path.abspath(__file__))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from app import run_app

if __name__ == "__main__":
    run_app()
