#!/usr/bin/env python3
"""Surgically add the MX4SIO icon to the committed SMS_IconsRGBA.c.

Why not a full re-bake: theme/icons/ (the bake source) is out of sync with the
shipping baked arrays -- its device PNGs are the OLD glossy icons, while the
committed SMS_IconsRGBA.c holds the artist's flat redesign. Re-baking would
regress USB/CDROM/CDDA/Host/DVD to the old art. So we inject ONE new array and
repoint g_RGBA_Dev[7] (the MX4SIO slot, currently a CDDA duplicate), leaving
every other shipping array byte-identical.

Idempotent: re-running replaces the injected array and re-points slot 7.
"""
import os, re, sys
from PIL import Image

ROOT = os.environ.get("ROOT", "/work")
PNG  = os.path.join(ROOT, "theme/icons/s_IconMX4SIO.png")
C    = os.path.join(ROOT, "SMS-v1/src/SMS_IconsRGBA.c")
SYM  = "rgba_s_IconMX4SIO"

def bake_bytes(path, expect=(48, 48)):
    im = Image.open(path).convert("RGBA")
    if im.size != expect:
        sys.exit("ERROR: %s is %s, expected %s" % (path, im.size, expect))
    px = im.tobytes()
    n = im.width * im.height
    out = bytearray(n * 4)
    for i in range(n):
        r, g, b, a = px[i*4], px[i*4+1], px[i*4+2], px[i*4+3]
        a2 = int(round(a * 128.0 / 255.0))
        if a2 <= 0:
            r = g = b = a2 = 0
        if a2 >= 0x80:
            a2 = 0x80
        out[i*4:i*4+4] = bytes((r, g, b, a2))
    return bytes(out)

def c_array(symbol, blob):
    lines = ["\t" + ",".join("0x%02x" % v for v in blob[o:o+16]) + ","
             for o in range(0, len(blob), 16)]
    return ("/* Hand-injected placeholder (tools/inject_mx4sio_icon.py); the theme/icons\n"
            " * bake source is stale for device icons, so this is added surgically. */\n"
            "static const unsigned char %s[ %d ] "
            "__attribute__(   (  aligned( 16 ), section( \".data\" )  )   ) = {\n%s\n};\n"
            % (symbol, len(blob), "\n".join(lines)))

def main():
    blob = bake_bytes(PNG)
    src = open(C).read()

    # 1) remove any prior injected array (idempotent)
    src = re.sub(r"(?:/\* Hand-injected[^\n]*\n \*[^\n]*\n)?static const unsigned char "
                 + re.escape(SYM) + r"\s*\[[^\]]*\][^=]*=\s*\{.*?\};\n", "", src, flags=re.S)

    # 2) insert the fresh array just before the first pointer table
    anchor = "\nconst unsigned char* const g_RGBA_Browser"
    idx = src.index(anchor)
    src = src[:idx] + "\n" + c_array(SYM, blob) + src[idx:]

    # 3) repoint g_RGBA_Dev slot 7 (last element) to the new symbol
    m = re.search(r"(const unsigned char\* const g_RGBA_Dev\s*\[\s*8\s*\]\s*=\s*\{)(.*?)(\};)",
                  src, flags=re.S)
    if not m:
        sys.exit("ERROR: g_RGBA_Dev[8] not found")
    items = [x.strip() for x in m.group(2).split(",") if x.strip()]
    if len(items) != 8:
        sys.exit("ERROR: g_RGBA_Dev has %d entries, expected 8" % len(items))
    items[7] = SYM
    new_dev = m.group(1) + "\n " + ",\n ".join(items) + "\n" + m.group(3)
    src = src[:m.start()] + new_dev + src[m.end():]

    open(C, "w", newline="\n").write(src)
    print("injected %s (%d bytes) and set g_RGBA_Dev[7] = %s" % (SYM, len(blob), SYM))

if __name__ == "__main__":
    main()
