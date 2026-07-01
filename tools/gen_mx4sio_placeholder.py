#!/usr/bin/env python3
"""Generate a flat microSD-card icon for the MX4SIO device slot (48x48 RGBA).

Placeholder art matching the artist's flat device redesign (bright blue, soft
shadow) so MX4SIO cards show a memory-card icon instead of the CDDA duplicate
that currently fills g_RGBA_Dev[7]. The blue is sampled from the approved USB
drive icon so the two removable-storage devices read as a matched pair.

Output: theme/icons/s_IconMX4SIO.png (48x48) + theme/_mx4sio_preview.png (10x).
The icon is injected into SMS_IconsRGBA.c by tools/inject_mx4sio_icon.py (the
theme/icons working folder is out of sync with the shipping baked arrays, so a
full re-bake would regress the flat device icons -- we inject surgically).
"""
import os
from collections import Counter
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.environ.get("ROOT", "/work")
APPROVED_USB = os.path.join(ROOT, "theme/approved/media_usb.png")
OUT   = os.path.join(ROOT, "theme/icons/s_IconMX4SIO.png")
PREV  = os.path.join(ROOT, "theme/_mx4sio_preview.png")

SS = 8               # supersample factor
N  = 48
W  = H = N * SS

def sample_blue():
    """Most common saturated-blue pixel in the approved USB icon."""
    im = Image.open(APPROVED_USB).convert("RGBA")
    c = Counter()
    for r, g, b, a in im.getdata():
        if a > 200 and b > 120 and b > r + 30 and b > g + 20 and (r + g + b) > 120:
            c[(r, g, b)] += 1
    if not c:
        return (46, 134, 222)
    return c.most_common(1)[0][0]

def darker(rgb, f=0.62):
    return tuple(int(v * f) for v in rgb)

def lighter(rgb, f=0.5):
    return tuple(int(v + (255 - v) * f) for v in rgb)

def s(v):  # scale 48px-space -> supersampled
    return int(round(v * SS))

def main():
    blue   = sample_blue()
    blue_d = darker(blue, 0.60)
    panel  = lighter(blue, 0.82)      # near-white label panel
    pins   = lighter(blue, 0.35)      # contact pins slightly lighter than body

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # --- soft drop shadow (matches the flat set) ---
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle([s(13.5), s(9.5), s(37), s(43)], radius=s(3),
                         fill=(6, 24, 44, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(s(2.2)))
    img = Image.alpha_composite(img, sh)

    # --- card body ---
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    bx0, by0, bx1, by1 = s(12), s(7), s(36), s(41)
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=s(3), fill=blue + (255,))
    # cut the top-right corner (the microSD bevel): carve it transparent
    bev = s(8)
    d.polygon([(bx1 - bev, by0 - 1), (bx1 + 1, by0 - 1), (bx1 + 1, by0 + bev)],
              fill=(0, 0, 0, 0))
    # redraw a crisp bevel edge for definition
    d.line([(bx1 - bev, by0), (bx1, by0 + bev)], fill=blue_d + (255,), width=s(1))
    d.line([(bx0, by1), (bx1, by1)], fill=blue_d + (120,), width=s(1))  # subtle base

    # label panel (upper area)
    d.rounded_rectangle([s(15), s(12), s(33), s(25)], radius=s(1.5),
                        fill=panel + (255,))

    # contact pins along the bottom (5 short bars)
    x = 15.5
    for _ in range(5):
        d.rounded_rectangle([s(x), s(30), s(x + 2.2), s(37)], radius=s(0.6),
                            fill=pins + (255,))
        x += 3.3

    img = Image.alpha_composite(img, card)

    small = img.resize((N, N), Image.LANCZOS)
    small.save(OUT)
    small.resize((N * 10, N * 10), Image.NEAREST).save(PREV)
    print("blue sampled:", blue, "-> wrote", OUT)

if __name__ == "__main__":
    main()
