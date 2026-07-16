#!/usr/bin/env python3
"""Dump the IRX import/export library tables of an IOP module.

Exists to gate the dev9 ABI trap documented in build_ata_bd_dev9v11.sh: IOP loadcore
binds a client to a provider by library NAME + MAJOR version only, then resolves every
stub BY ORDINAL. A module built against dev9 v1.9 silently lands on the wrong ordinals
when SMS's embedded dev9 v1.1 clone (iop/SMSDev9) provides the library -- the DMA
callback is never armed and the transfer hangs or never starts. It is not a load error,
so nothing reports it: the only way to catch it is to read the tables.

Usage:
    python3 irx_imports.py <file.irx> [...]        # human readable
    python3 irx_imports.py --assert dev9=1.1 f.irx # exit 1 unless the binding matches
"""

import struct
import sys

IMPORT_MAGIC = 0x41E00000
EXPORT_MAGIC = 0x41C00000

# struct irx_import_table { u32 magic; ptr next; u16 version; u16 mode; char name[8]; ... }
HDR = 20
STUB_JR_RA = 0x03E00008


def _tables(buf, magic):
    """Yield (offset, name, major, minor, [ordinals]) for each table with `magic`."""
    out = []
    needle = struct.pack("<I", magic)
    pos = 0
    while True:
        pos = buf.find(needle, pos)
        if pos < 0:
            return out
        if pos + HDR <= len(buf):
            version, mode = struct.unpack_from("<HH", buf, pos + 8)
            raw = buf[pos + 12 : pos + 20]
            name = raw.split(b"\x00")[0].decode("ascii", "replace")
            # A real table's name is printable ASCII; the magic can also occur as data.
            if name and all(32 <= c < 127 for c in raw.rstrip(b"\x00")):
                out.append(
                    (pos, name, version >> 8, version & 0xFF, _ordinals(buf, pos + HDR, magic))
                )
        pos += 4


def _ordinals(buf, off, magic):
    """Import stubs are 2 words: `jr $ra` then `addiu $zero,$zero,<ordinal>`."""
    if magic != IMPORT_MAGIC:
        return []
    ords_ = []
    while off + 8 <= len(buf):
        w0, w1 = struct.unpack_from("<II", buf, off)
        if w0 == 0 and w1 == 0:
            break
        if w0 != STUB_JR_RA:
            break
        ords_.append(w1 & 0xFFFF)
        off += 8
    return sorted(ords_)


def _read_module(path):
    """Return the raw IRX bytes, transparently XZ-decompressing a .xz input.

    The build embeds the .irx.xz blobs, not the plain .irx -- so the ABI gate must be
    able to assert on the SHIPPED bytes. A gate that only ever saw the plain .irx could
    be bypassed by committing a re-bound .xz alone (nothing regenerates the pair)."""
    buf = open(path, "rb").read()
    if path.endswith(".xz") or buf[:6] == b"\xfd7zXZ\x00":
        import lzma
        buf = lzma.decompress(buf, format=lzma.FORMAT_XZ)
    return buf


def dump(path):
    buf = _read_module(path)
    imports = _tables(buf, IMPORT_MAGIC)
    exports = _tables(buf, EXPORT_MAGIC)
    print("=== %s (%d bytes)" % (path, len(buf)))
    for _, name, maj, minor, ords_ in exports:
        print("  EXPORTS %-10s v%d.%d" % (name, maj, minor))
    for _, name, maj, minor, ords_ in imports:
        shown = ",".join(str(o) for o in ords_)
        print("  imports %-10s v%d.%d  ordinals={%s}" % (name, maj, minor, shown))
    return imports


def main():
    args = sys.argv[1:]
    want = {}
    while args and args[0] == "--assert":
        lib, ver = args[1].split("=")
        maj, minor = ver.split(".")
        want[lib] = (int(maj), int(minor))
        args = args[2:]

    if not args:
        print(__doc__)
        return 2

    rc = 0
    for path in args:
        imports = dump(path)
        for lib, (maj, minor) in want.items():
            got = [(a, b) for _, n, a, b, _ in imports if n == lib]
            if not got:
                print("  !! ASSERT FAIL: %s imports no '%s' table" % (path, lib))
                rc = 1
            elif (maj, minor) not in got:
                print(
                    "  !! ASSERT FAIL: %s imports %s v%s -- expected v%d.%d"
                    % (path, lib, "/".join("%d.%d" % g for g in got), maj, minor)
                )
                rc = 1
            else:
                print("  ok ASSERT: %s imports %s v%d.%d" % (path, lib, maj, minor))
    return rc


if __name__ == "__main__":
    sys.exit(main())
