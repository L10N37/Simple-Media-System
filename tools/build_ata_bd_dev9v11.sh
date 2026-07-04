#!/bin/sh
# Rebuild ata_bd.irx bound to SMS's dev9 v1.1 ABI (fixes the ATA exFAT-mount hang).
#
# ROOT CAUSE (diagnosed + adversarially verified against the binaries):
#   The stock ps2sdk ata_bd.irx is compiled against dev9 *v1.9*, but SMS embeds a
#   dev9 *v1.1* clone (SMS-v1/iop/SMSDev9). IOP loadcore links a client to a provider
#   by library NAME + MAJOR version only, then resolves every stub BY ORDINAL. The
#   DMA-callback ordinals moved between those dev9 versions:
#       v1.1 (SMS):  11 = dev9RegisterPreDmaCb   12 = dev9RegisterPostDmaCb   (no 13)
#       v1.9 (sdk):  11 = Dev9RegisterPowerOffHandler  12 = PreDmaCb  13 = PostDmaCb
#   So the stock ata_bd's dev9RegisterPreDmaCb(0,...) (emitted at ord 12) lands on
#   SMS's PostDmaCb, its PostDmaCb(ord 13) is null-stubbed/dropped, and its
#   PowerOffHandler(15,...) (ord 11) lands on SMS's PreDmaCb -> writes index 15 of a
#   [2]-element array (OOB). Net: dev9_pre_dma_cbs[0] is never set, so the SPEED
#   engine's XFR_CTRL |= 0x80 is never armed before the sector-read DMA, and the
#   unbounded `while (chcr & DMAC_CHCR_TR)` busy-loop in dev9DmaTransfer spins forever.
#   => the drive spins up (IDENTIFY is PIO), but the exFAT mount's DMA read HANGS.
#   Only ATA imports dev9 (USB=usbd, MX4SIO=SIO2, iLink=IEEE1394), and the retail
#   PS2ATAD/PFS path imports only dev9 ords {4,5,7,8} -> both are unaffected.
#
# FIX (this script): rebuild ata_bd from ps2sdk source but pointed at SMS's v1.1 dev9
#   ordinals, and drop the PowerOffHandler registration (SMS v1.1 has no such export;
#   SMS handles poweroff via its own SMSPWROFF module). Zero change to any other module.
#
# Requires: the ps2sdk SOURCE tree (refs/ps2sdk) and the ps2dev/ps2dev:v2.0.0 image
# (IOP toolchain mipsel-none-elf-gcc). Run from the repo root (parent of refs/ + SMS-v1/).
#
#   sh SMS-v1/tools/build_ata_bd_dev9v11.sh
#
# Output: SMS-v1/irx/ata_bd.irx (v1.1-bound) + SMS-v1/irx/ata_bd.irx.xz (regenerated).
# Verify the rebind with: python3 SMS-v1/tools/../<irx parser> -> dev9 version 0x0101,
#   ordinals {4,5,7,8,10,11,12} (NO 13, NO PowerOff).
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"     # repo root
PS2SDK_SRC="$REPO/refs/ps2sdk"
OUT="$REPO/SMS-v1/irx"

docker run --rm -v "$PS2SDK_SRC":/ps2sdksrc:ro -v "$OUT":/out ps2dev/ps2dev:v2.0.0 sh -c '
  set -e
  apk add --no-cache build-base >/dev/null 2>&1     # host cc (for srxfixup) + make
  cp -r /ps2sdksrc /tmp/src; rm -rf /tmp/src/.git; cd /tmp/src

  # (1) dev9 import header: v1.9 -> v1.1 ordinals
  sed -i "s/DECLARE_IMPORT_TABLE(dev9, 1, 9)/DECLARE_IMPORT_TABLE(dev9, 1, 1)/"          iop/dev9/dev9/include/dev9.h
  sed -i "s/DECLARE_IMPORT(12, dev9RegisterPreDmaCb)/DECLARE_IMPORT(11, dev9RegisterPreDmaCb)/"   iop/dev9/dev9/include/dev9.h
  sed -i "s/DECLARE_IMPORT(13, dev9RegisterPostDmaCb)/DECLARE_IMPORT(12, dev9RegisterPostDmaCb)/" iop/dev9/dev9/include/dev9.h
  # (2) drop the PowerOffHandler import (SMS v1.1 dev9 has no such export)
  sed -i "/I_Dev9RegisterPowerOffHandler/d" iop/dev9/atad/src/imports.lst
  # (3) drop the PowerOffHandler(15,...) registration call (keep the cb referenced)
  sed -i "s/Dev9RegisterPowerOffHandler(15, &ata_shutdown_cb);/(void)ata_shutdown_cb;/" iop/dev9/atad/src/ps2atad.c

  export PS2SDKSRC=/tmp/src
  export PATH="/usr/local/ps2dev/iop/bin:/usr/local/ps2dev/ee/bin:$PATH"
  make -C iop/dev9/ata_bd >/dev/null
  cp iop/dev9/ata_bd/irx/ata_bd.irx /out/ata_bd.irx
  echo "built ata_bd.irx ($(wc -c < /out/ata_bd.irx) bytes)"
'

# Regenerate the committed XZ blob (CRC32 / LZMA2, matching SMS's embedded decoder).
python3 - "$OUT/ata_bd.irx" <<'PY'
import sys, lzma
irx = sys.argv[1]
b = open(irx, "rb").read()
c = lzma.compress(b, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32,
                  filters=[{"id": lzma.FILTER_LZMA2, "preset": 9, "dict_size": 1 << 20}])
open(irx + ".xz", "wb").write(c)
assert lzma.decompress(c, format=lzma.FORMAT_XZ) == b
print("ata_bd.irx.xz %d bytes (round-trip OK)" % len(c))
PY
