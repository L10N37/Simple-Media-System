# MX4SIO support in SMS — implementation notes

Adds MX4SIO (microSD over the PS2 SIO2 port, via the modern PS2SDK BDM stack) as
a media source in SMS, on top of KrahJohlito's BDM groundwork.

## Why it was hard (three layered bugs)

The card mounted and directories listed for prior attempts, but **playing a file
hard-froze the console.** It turned out to be three separate problems stacked on
top of each other:

1. **Hard IOP lock — unbounded SIO2 busy-waits.** `mx4sio_bd` spins on the SIO2
   "transfer complete" status bit with no bound — *including inside the DMA
   completion ISR* (interrupts masked). If any transfer stalls, the whole IOP
   locks solid and the EE hangs with it. A thread-level watchdog can't break it
   because the lock is in interrupt context.

2. **IOP RAM exhaustion.** SMS auto-loads the full HDD stack (PS2ATAD/PS2HDD/
   **PS2FS — ~40-48 buffers**) and the network stack (PS2IP ~67 KB + SMAP) at
   boot. Co-resident with the BDM stack (bdm, bdmfs_fatfs ~36 KB, iomanx,
   mx4sio_bd, usbmass_bd, sio2man) + mcman/padman/audsrv, the 2 MB IOP runs out,
   and the first large file read locks instead of failing cleanly.

3. **The real wall — legacy `fio` can't do large reads on BDM.** SMS's file I/O
   uses the legacy FILEIO (`fio*`) API. Bridged to the BDM filesystem it works
   for **small** reads (≤ ~4 KB) but **hangs on larger ones** (16 KB and 256 KB
   both hang; 4 KB works). Format detection reads 4 KB at a time and always
   worked; playback streams in 256 KB chunks and always hung. This is the wall
   both prior devs hit — and it is *size*, not the seek (the `fioLseek`
   returned the correct offset; a 4 KB read after the same seek works).

## The fixes

**A. Driver — `iop/sio/mx4sio_bd/src/` (patches in `patches/`, rebuilt IRX in `irx/`):**
- `spisd_read`: split each request into `SPISD_MAX_BATCH` (32) sector batches and
  advance the sector on partial reads (fixes a latent bug).
- `spisd_read_multi_do`: replace the no-timeout `WaitEventFlag` with a bounded
  `PollEventFlag` poll (watchdog) so a missing DMA interrupt can't hang forever.
- `mx_sio2_xfer_done()`: bound every SIO2 "transfer complete" spin (incl. the
  in-ISR ones) so a stalled transfer becomes a recoverable error, never a lock.

**B. App — `src/SMS_FileContext.c`:**
- Cap the `mass:` streaming buffer to **4 KB** (`STIO_Stream`), so every read
  stays in the size range the legacy `fio`/BDM path can satisfy. Scoped to
  `mass:` so HDD/CD/DVD/SMB are unaffected.

**C. Module loading — `src/SMS_IOP.c` (KrahJohlito):**
- BDM stack load order: iomanx → bdm → bdmfs_fatfs → sio2man (swapped in for
  rom0:SIO2MAN) → mcman/mcserv/padman; then usbd + usbmass_bd + mx4sio_bd.
- `sbv_patch_fileio()` bridges legacy `fio*` to the IOMANX/BDM devices.

## Result

AVI (XviD/MP3) and MP3 play **smoothly** from an MX4SIO microSD on real hardware
(tested: SCPH-7xxx-9xxx slim). The card appears as a `mass:` device alongside USB.

## Build

```
docker run --rm -v "<repo>":/src -w /src ps2dev/ps2dev:v1.0 sh -c 'apk add build-base && make all'
```
Produces `bin/SMS.elf`.

## Still to do
- HDD/network coexistence (lazy-load if IOP RAM is tight with everything on).
- Memory-card detection regression from the sio2man swap.
- SMB modernization (libsmb2 for SMB2/3, or smbman).
- Optional: route `mass:` I/O through `fileXio` (native BDM, no read-size limit)
  to lift the 4 KB cap for max throughput.
