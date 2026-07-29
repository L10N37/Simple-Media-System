# Hardened freesd sources

These are ps2sdk's `iop/sound/libsd` sources with three unbounded spins bounded. They are
copied over the pristine tree by `tools/build_libsd.sh` immediately before the module is
built, so `refs/ps2sdk` stays untouched.

## Why this exists

SMS ships freesd only as a fallback for consoles whose BIOS has no `rom0:LIBSD` — the PSX /
DESR. **Every retail PS2 loads Sony's LIBSD and never executes a line of this code**, so
nothing here can affect one. A DESR is the only machine where AUDSRV runs against freesd
instead of Sony's driver, which makes it the only machine that can hit freesd's own bugs.

## The bug being defended against

`TransIntrData[core].mode` selects, at interrupt time, whether a completed SPU2 DMA was a
**voice** transfer or a **block** transfer:

- `sceSdVoiceTrans` sets `mode = chan` — bit 0x100 CLEAR (`voice.c`, `VoiceTransDma`)
- `sceSdBlockTrans` sets `mode = 0x100 | core` — bit 0x100 SET (`block.c`)

Voice and block transfers **share that one field per core**, and nothing serialises them.
SMS's AUDSRV uses both: voice transfers to upload the UI sound bank and play UI sounds,
block transfers (looping, self-rearming) to stream audio during playback. So the two
overlap the moment a file starts playing, and the field can describe the wrong transfer.

Misrouting is fatal in **both** directions, and freesd has no escape from either:

1. **Block completion routed to the voice branch.** The voice branch spins on two SPU2
   status bits (`freesd.c`, `TransInterrupt`) that will never settle, because no voice
   transfer is in flight. This runs **inside an interrupt handler**, so the IOP spins with
   interrupts disabled and the whole console dies — a total freeze, EE included.
2. **Voice completion routed to the block branch.** `VoiceTransComplete[chan]` is then never
   set, and `sceSdVoiceTransStatus(chan, 1)` — ordinal 19, which SMS's AUDSRV imports —
   spins forever waiting for it (`voice.c`). That is thread level, so the IOP survives, but
   it is an RPC server thread, so the EE caller blocks forever too.

Those two outcomes look different on a TV: (1) freezes the clock, (2) leaves it ticking.
Both leave whatever was last drawn on screen. That is why this is worth fixing without
first establishing which one a tester saw — it is the same root cause either way.

## What was changed

Three `while (...)` loops gained an iteration limit. Nothing else. No behaviour changes on
a healthy SPU2, which settles these bits in well under a microsecond:

| File | Function | Limit |
|---|---|---|
| `freesd.c` | `TransInterrupt`, voice branch, `statx & 0x80` | `SMS_SPIN_LIMIT` (1e6) |
| `freesd.c` | `TransInterrupt`, voice branch, `CORE_ATTR & 0x30` | `SMS_SPIN_LIMIT` (1e6) |
| `voice.c`  | `sceSdVoiceTransStatus`, `!VoiceTransComplete` | `SMS_VOICE_WAIT_LIMIT` (2e7) |

The interrupt-level limit is the tighter of the two on purpose: time spent there is time
the IOP is deaf. The thread-level one is loose because giving up early there truncates a
sample for no reason.

This bounds the damage; it does not remove the underlying race. Properly fixing that means
either serialising voice against block transfers per core, or tracking the two kinds of
transfer in separate state — a redesign of a driver we cannot test on the one console that
runs it. Bounding the spins turns a dead console into, at worst, a click.

## Drift gate

`build_libsd.sh` checks the upstream files these were derived from still hash as recorded in
`upstream.sha256`. If ps2sdk changes them, the build FAILS rather than silently pinning stale
copies — re-derive the patch against the new upstream, refresh the hashes, and re-verify.
