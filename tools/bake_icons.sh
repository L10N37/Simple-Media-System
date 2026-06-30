#!/bin/sh
# Regenerate src/SMS_IconsRGBA.c from theme/icons/*.png, then rebuild SMS to
# embed the new icons. This is the whole "edit a PNG -> it's in the game" loop.
#
# Usage (from the SMS-v1 root):   sh tools/bake_icons.sh
# Requires Docker. The helper image (python + Pillow) is built on first run.
#
# Icons are plain RGBA PNGs (theme/icons/<name>.png). Keep the dimensions:
#   48x48 for device icons (USB/CDROM/HDD/CDDA/Host/DVD/SMB), 32x32 for the rest.
# Transparency is real 8-bit alpha (baked to the PS2's 0..0x80 scale). The legacy
# IPU/"MPEG-Intra" blobs are no longer used for icons.
set -e
cd "$(dirname "$0")/.."
docker image inspect sms-ipu-tools >/dev/null 2>&1 || \
  docker build -t sms-ipu-tools -f tools/Dockerfile.ipu tools/
docker run --rm -v "$PWD":/work \
  -e ICON_DIR=/work/theme/icons -e RGBA_OUT=/work/src/SMS_IconsRGBA.c \
  sms-ipu-tools python3 /work/tools/bake_icons_rgba.py
echo
echo "Regenerated src/SMS_IconsRGBA.c. Now rebuild SMS (make) to embed the icons."
