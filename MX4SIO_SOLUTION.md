# MX4SIO support in SMS — developer review document

This document explains, for a reviewer, **what changed, why, and how it fixes the
problem** so the MX4SIO work can be confirmed and greenlit. It is written to be
read top-to-bottom alongside the diff (`git diff <upstream>..mx4sio`).

---

## 1. Summary

This branch makes **SMS (Simple Media System) play media directly from an MX4SIO
microSD card** on real PS2 hardware. It builds on KrahJohlito's earlier BDM
groundwork (which got the card to *mount and list* but **hard-froze on playback**)
and adds the fixes that make file **reads actually complete**, so video and audio
play smoothly.

Verified on real hardware (SCPH-7xxx–9xxx slim, HDD+network adapter present):
a 640×480 XviD/MP3 AVI and an MP3 both play smoothly off an MX4SIO microSD.

The build target is the project's pinned toolchain, **`ps2dev/ps2dev:v1.0`**
(the tag SMS's own CI uses).

---

## 2. Background a reviewer needs

**How SMS reads storage.** SMS embeds its IOP driver modules and loads them at
boot. Its EE-side file layer (`src/SMS_FileContext.c`) talks to storage through
the **legacy FILEIO (`fio*`) API** — `fioOpen/fioRead/fioLseek/fioClose` for files
and `fioDopen/fioDread` for directories. (This was a deliberate upstream choice;
`src/SMS_FileContext.c` even carries the note *"Anyone is free to replace fioxxx
by fileXioxxx."*) A storage device shows up in the GUI when the IOP posts a mount
message; each source is gated by a `g_IOPFlags` bit and indexed by `g_CMedia`
into the `g_pDevName[]` table in `src/SMS_FileDir.c`.

**What MX4SIO is.** MX4SIO is a microSD adapter on the PS2's SIO2 (controller)
port. In the modern PS2SDK it is a **BDM (Block Device Manager)** block device:
`mx4sio_bd.irx` provides the block device, `bdm.irx` + `bdmfs_fatfs.irx` provide
the FAT/exFAT filesystem, and the card appears as a `mass:` device — the same
abstraction OPL/NHDDL use. MX4SIO hooks the PS2SDK `sio2man` so it can share the
SIO2 bus with the controller (`padman`) and memory card (`mcman`).

**Why it's an SMS-specific problem.** The MX4SIO BDM driver works fine in OPL,
NHDDL and wLaunchELF. It did **not** work in SMS because SMS exercises it
differently — it keeps the IOP heavily loaded (audio, GUI, continuous pad
polling) *during* reads, and it reads in large chunks through the legacy `fio`
path. The bugs below only surface under those conditions, which is why two prior
developers (one an OPL/BDM maintainer) got the card mounting but stalled on
playback.

---

## 3. The problem: three layered bugs

The symptom was "card mounts, folders list, **opening a file hard-freezes the
console**." It was three distinct bugs stacked:

### Bug 1 — Unbounded SIO2 busy-waits hard-lock the IOP
`mx4sio_bd` waits for each SIO2 transfer to finish by spinning on a status bit
with **no bound**, including **inside the DMA-completion interrupt handler**
(`mx_sio2_dma_isr_rx`, interrupts masked):
```c
while ((inl_sio2_stat6c_get() & (1 << 12)) == 0)
    ;
```
If a transfer ever stalls (e.g. SIO2 contention while SMS polls the pad), that
spin never returns. In the ISR it runs with interrupts off → **the entire IOP
locks → the EE hangs waiting on it → a true hard freeze** that no EE/thread-level
timeout can break. (We proved the freeze was *here* and not in the higher-level
wait: bounding the thread-side `WaitEventFlag` did not stop it; bounding the
ISR-side spins did.)

### Bug 2 — IOP RAM exhaustion when the HDD + network stacks co-load
SMS auto-loads the full HDD stack (`PS2ATAD`/`PS2HDD`/`PS2FS` — `PS2FS` alone
asks for ~40–48 buffers) and the network stack (`PS2IP` ~67 KB + `SMAP`) at boot.
Co-resident with the BDM stack (`bdm`, `bdmfs_fatfs` ~36 KB, `iomanx`,
`mx4sio_bd`, `usbmass_bd`, `sio2man`) plus `mcman`/`padman`/`audsrv`, the **2 MB
IOP runs out of memory**, and the first large read locks instead of failing
cleanly. Removing the HDD/network stacks turned the hard freeze into a recoverable
soft hang — confirming RAM pressure was a contributor to the *hard* lock.

### Bug 3 (the wall) — the legacy `fio` path can't do large reads on BDM
With the lock and RAM issues handled, one wall remained: a **large single
`fioRead` hangs on the BDM/MX4SIO device, while a small one works.** Measured on
hardware via on-screen instrumentation:
- format detection reads **4 KB** at a time → **always worked**;
- playback streams in **256 KB** chunks → **always hung**, and a **16 KB** read
  hung too;
- the `fioLseek` before the read returned the **correct** offset, and a **4 KB**
  read after that same seek worked — so it is **read size**, not the seek, not the
  offset.

This is the exact wall both prior developers hit, and it matches the upstream
author's own "replace fioxxx by fileXioxxx" note: the legacy FILEIO read path,
bridged to the modern BDM filesystem, cannot satisfy a large single transfer.

---

## 4. How we diagnosed it (why these fixes, not guesses)

Because there is no serial/IOP-TTY on the target, root-causing was done with
**on-screen instrumentation** (temporary `GUI_Status` markers, since removed) and
**one-variable-at-a-time hardware tests**. The chain of eliminations:
read size at the driver level → ruled out (1-sector reads still hung) → ISR
busy-wait identified as the hard-lock → RAM identified via stripping HDD/network
(hard freeze → soft hang) → markers showed reads *succeeding* at 4 KB and the
hang isolated to `STIO_Stream`'s 256 KB read **after** a successful `lseek`,
proving the EE-level read-size limit. Each fix below targets a confirmed cause.

---

## 5. The changes

### Part A — BDM integration (foundation, by KrahJohlito)
These files set up the modern BDM stack and are KrahJohlito's groundwork, carried
over and built on here:

| File | Purpose |
|---|---|
| `Makefile` | `BDM` build option; embeds the IRX in `irx/` via `bin2c`; links `-lmc -lpadx` |
| `irx/*.irx` | the embedded modern modules: `iomanx`, `bdm`, `bdmfs_fatfs`, `sio2man`, `mx4sio_bd`, `usbmass_bd`, `usbd`, `mcman`, `mcserv`, `padman` (+ `filexio`) |
| `src/SMS_IOP.c` | loads the BDM stack (iomanx→bdm→bdmfs_fatfs→sio2man→mcman/mcserv/padman, then usbd/usbmass_bd/mx4sio_bd); `sbv_patch_fileio()` bridges `fio*` to the IOMANX/BDM devices; probes `massN:` |
| `include/SMS_PAD.h`, `src/SMS_PAD.c` | swapping `rom0:SIO2MAN` for the PS2SDK `sio2man` (so MX4SIO can hook it) requires driving the pad via `libpad` |
| `include/SMS_MC.h`, `src/SMS_MC.c` | likewise the memory card via `libmc` |
| `src/SMS_FileDir.c`, `src/SMS_GUI.c`, `src/SMS_GUIDevMenu.c` | surface the `mass:` device in the browser/device menu |
| `include/SMS.h`, `src/SMS_GUIMenuSMS.c`, `src/SMS_History.c`, `src/SMS_Config.c` | supporting glue for the libmc/libpad switch |

> Note: `src/SMS_Config.c` / `src/SMS_GUIMenuSMS.c` contain a **memory-card
> detection workaround** (loosened `MC_GetInfo` threshold) introduced by the
> sio2man swap. It is a known rough edge — see §8.

### Part B — Our fixes

**B1. Driver: never hang the IOP, and survive a stalled transfer**
`patches/mx4sio_bd-sms.patch` (applied to the PS2SDK `iop/sio/mx4sio_bd/` source;
the result is the embedded `irx/mx4sio_bd.irx`). Three changes:
- **Bound every SIO2 "transfer complete" spin** with `mx_sio2_xfer_done()`
  (`mx4sio.c`), including the in-ISR ones — a stalled transfer becomes a
  recoverable error, never an IOP lock. *(fixes Bug 1)*
- **Watchdog the completion wait** — `spisd_read_multi_do` (`spi_sdcard_driver.c`)
  replaces the no-timeout `WaitEventFlag` with a bounded `PollEventFlag` loop, so a
  missing DMA interrupt can't block forever. Adds `I_PollEventFlag` to
  `imports.lst`.
- **Batch multi-block reads** — `spisd_read` splits a request into
  `SPISD_MAX_BATCH` (32) sector batches and (fixing a latent bug) advances the
  sector number on a partial read.

**B2. App: keep `mass:` reads within the size that works** — `src/SMS_FileContext.c`
This is the change that makes playback succeed. In `STIO_Stream`, cap the
streaming buffer to **4 KB for `mass:` devices only**, so every read stays in the
size range the legacy FILEIO/BDM path satisfies: *(fixes Bug 3)*
```c
apCtx -> m_BufSize = anBlocks * 4096;
#ifndef _WIN32
/* MX4SIO/BDM: a large single read over the legacy FILEIO path hangs; cap the
 * streaming buffer for 'mass' devices so every read stays in the working size
 * range. Scoped to mass so HDD/CD/DVD/SMB throughput is unaffected. */
if ( apCtx -> m_pPath != NULL && strncmp ( apCtx -> m_pPath, "mass", 4 ) == 0 && apCtx -> m_BufSize > 4096 )
 apCtx -> m_BufSize = 4096;
#endif
```
The cap is scoped to `mass:` by inspecting the file path, so HDD/CD/DVD/SMB are
completely unaffected. Playback at 4 KB is smooth in testing.

*(Bug 2 — IOP RAM — is addressed operationally: with the bounded driver in place
the RAM pressure no longer produces a hard lock; if HDD+network+MX4SIO cannot all
co-reside on a given console, the planned follow-up is lazy-loading each storage
stack on demand. See §8.)*

---

## 6. Build & reproduce

```sh
# 1) (optional) rebuild the custom driver IRX from a ps2sdk source checkout:
cd <ps2sdk>; patch -p1 < patches/mx4sio_bd-sms.patch
cd iop/sio/mx4sio_bd && PS2SDKSRC=<ps2sdk> make      # -> irx/mx4sio_bd.irx
# copy it into this repo's irx/

# 2) build the EE app with the project's pinned toolchain:
docker run --rm -v "$PWD":/src -w /src ps2dev/ps2dev:v1.0 \
  sh -c 'apk add --no-cache build-base && make all'     # -> bin/SMS.elf
```
The embedded IRX are committed in `irx/` so step 2 works without step 1.

---

## 7. Testing performed

- Real hardware, PS2 slim with HDD + network adapter.
- XviD/MP3 AVI (640×480) and MP3 played off an MX4SIO microSD (FAT32): **smooth.**
- Card detected and selectable as a `mass:` device; directory browsing works.
- Diagnosis was done with temporary on-screen instrumentation (removed in this
  branch); the production code contains only the fixes above.

---

## 8. Known limitations / planned follow-ups

Honest list for the reviewer:
1. **HDD + network coexistence** with MX4SIO is being finalized; if a console
   can't hold all stacks in IOP RAM at once, the fix is lazy-loading storage
   modules on demand rather than all at boot.
2. **Memory-card detection** carries a threshold workaround from the sio2man swap
   (`SMS_Config.c`/`SMS_GUIMenuSMS.c`); to be replaced with a proper fix.
3. **SMB** is unrelated to MX4SIO and remains the legacy SMBv1 stack (broken
   against modern Windows/Samba); modernizing it (libsmb2 / smbman) is separate
   future work.
4. **Throughput headroom:** the 4 KB cap is a simple, robust fix and is smooth in
   testing. Routing `mass:` I/O through `fileXio` (the native BDM API, no
   read-size limit) would lift the cap entirely — an optional future improvement,
   exactly the "replace fioxxx by fileXioxxx" path the original author suggested.

---

## 9. Credits

- **Eugene Plotnikov** — original SMS.
- **KrahJohlito** — BDM/MX4SIO integration groundwork (module loading, libpad/
  libmc switch, device-menu wiring).
- This branch — the driver hardening (busy-wait bounds, completion watchdog, read
  batching) and the `mass:` read-size cap that make playback actually work, plus
  this documentation.
