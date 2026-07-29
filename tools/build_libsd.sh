#!/bin/sh
# Build ps2sdk's libsd (freesd) as an embeddable IRX for SMS.
#
# WHY THIS EXISTS
#   SMS loads the sound driver from the console BIOS: SifLoadModule("rom0:LIBSD").
#   The PSX / DESR BIOS HAS NO rom0:LIBSD. Its ROM carries PLIBSD (the XMB variant,
#   v3.4) and TLIBSD (testmode, v1.4), and neither is a drop-in for the standard
#   module. Reported by GhostTownUS on a DESR-7100, root-caused by israpps from a
#   DESR-5000 ROM dump. The same is reportedly true of protokernel consoles.
#
#   Result on those machines: LIBSD fails to load -> AUDSRV cannot resolve its imports
#   and never loads -> no audio RPC server exists -> SMS has no sound. (It also used to
#   HANG there; that is fixed separately in SIF_BindRPC.)
#
#   Shipping our own libsd removes the BIOS dependency entirely: SMS falls back to this
#   embedded copy whenever rom0:LIBSD is missing, and a PSX gets real audio rather than
#   a mute media player.
#
# THE ABI GATE (same class of trap as build_udpfs.sh's dev9 v1.1 check)
#   IOP loadcore binds a client to a library by NAME + MAJOR version only, then resolves
#   every stub BY ORDINAL. SMS's AUDSRV blob imports:
#       libsd v1.4  ordinals {4,5,7,9,11,15,17,18,19,20,26,27}
#   ps2sdk's freesd exports libsd (1,4) with those ordinals mapping to:
#       4 sceSdInit          5 sceSdSetParam       7 sceSdSetSwitch
#       9 sceSdSetAddr      11 sceSdSetCoreAttr   15 sceSdProcBatch
#      17 sceSdVoiceTrans   18 sceSdBlockTrans    19 sceSdVoiceTransStatus
#      20 sceSdBlockTransStatus  26 sceSdSetTransIntrHandler  27 sceSdSetSpu2IntrHandler
#   -- every one a real function, none a _retonly stub. That is what makes it a genuine
#   drop-in rather than a module that loads clean and then does nothing. The assert at
#   the bottom re-checks it on every build. DO NOT REMOVE IT.
#
# Requires the ps2dev/ps2dev:v2.0.0 image (IOP toolchain). Run from anywhere:
#   sh SMS-v1/tools/build_libsd.sh

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
SMS=$(cd "$HERE/.." && pwd)
# Mount the WHOLE ps2sdk tree: the module Makefile pulls in $(PS2SDKSRC)/Defs.make and
# the iop/Rules.*.make chain, so building the subdirectory in isolation cannot work.
SRC=$(cd "$SMS/../refs/ps2sdk" && pwd)

DSRC=$(cd "$SRC" && pwd -W 2>/dev/null || echo "$SRC")
DOUT=$(cd "$SMS/irx" && pwd -W 2>/dev/null || echo "$SMS/irx")
DPAT=$(cd "$HERE/libsd" && pwd -W 2>/dev/null || echo "$HERE/libsd")

# DRIFT GATE. Our hardened freesd sources ( tools/libsd, see README-SMS.md there ) were
# derived from these exact upstream files. If ps2sdk changes them, FAIL rather than quietly
# building stale pinned copies and losing whatever upstream fixed.
( cd "$SRC/iop/sound/libsd/src" && sha256sum -c "$HERE/libsd/upstream.sha256" ) || {
  echo "ERROR: ps2sdk's libsd sources changed since tools/libsd was derived from them." >&2
  echo "       Re-derive the three bounded spins against the new upstream, refresh" >&2
  echo "       tools/libsd/upstream.sha256, and re-verify. Do NOT just update the hashes." >&2
  exit 1
}

MSYS_NO_PATHCONV=1 docker run --rm -v "$DSRC":/src -v "$DPAT":/patched -v "$DOUT":/out ps2dev/ps2dev:v2.0.0 sh -c '
  set -e
  apk add --no-cache build-base >/dev/null 2>&1     # image ships no make/host cc
  cp -r /src /tmp/ps2sdk && cd /tmp/ps2sdk

  # Overlay the hardened sources onto the pristine copy INSIDE the container, so refs/ps2sdk
  # is never modified on the host. Three unbounded spins get an escape count -- a misrouted
  # SPU2 transfer completion must not be able to hang the IOP inside an interrupt handler.
  cp /patched/freesd.c /patched/voice.c /tmp/ps2sdk/iop/sound/libsd/src/
  export PATH="/usr/local/ps2dev/iop/bin:/usr/local/ps2dev/ee/bin:$PATH"
  export PS2SDKSRC=/tmp/ps2sdk

  make -C iop/sound/libsd clean >/dev/null 2>&1 || true
  make -C iop/sound/libsd all

  find /tmp/ps2sdk/iop/sound/libsd -name "*.irx" -exec cp {} /out/libsd.irx \;
'

echo "built libsd.irx ($(stat -c%s "$SMS/irx/libsd.irx") bytes)"

# ABI gate: the module must still export libsd v1.4 with every ordinal AUDSRV imports.
python "$HERE/irx_imports.py" --exports "$SMS/irx/libsd.irx" 2>/dev/null || \
  python "$HERE/irx_imports.py" "$SMS/irx/libsd.irx"

# compress_irx.py takes its directory from IRX_DIR and IGNORES argv -- passing a path here
# silently compressed nothing, leaving a stale .xz to be embedded while the freshly built
# .irx sat unused next to it. It rebuilds every module's .xz in the directory, which is fine:
# the compression is deterministic, so unchanged modules re-emit byte-identical output.
IRX_DIR="$SMS/irx" python "$HERE/compress_irx.py"
