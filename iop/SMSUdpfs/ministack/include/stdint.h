/* Minimal stdint.h shim -- the ps2dev IOP toolchain (iop-gcc) ships none, but neutrino's
 * smap/ministack/udpfs headers include <stdint.h> for fixed-width types and bitfields.
 *
 * CRITICAL: these MUST match ps2sdk's IOP typedefs, not just the right WIDTH. ps2sdk
 * common/include/tamtypes.h:43-49 does `#ifdef _IOP  typedef unsigned long u32;` while
 * the _EE branch (:29-30) uses `unsigned int`. Both are 32-bit on MIPS ILP32, but they
 * are DISTINCT TYPES to the compiler: typing uint32_t as `unsigned int` makes every
 * `uint32_t*` -> `u32*` argument (e.g. WaitEventFlag's resbits, thevent.h:69) a
 * -Wincompatible-pointer-types error. Keep uint32_t/int32_t on `long` to match _IOP.
 */
#ifndef _SMS_IOP_STDINT_SHIM_H
#define _SMS_IOP_STDINT_SHIM_H

typedef unsigned char      uint8_t;
typedef signed char        int8_t;
typedef unsigned short     uint16_t;
typedef signed short       int16_t;
typedef unsigned long      uint32_t;   /* == ps2sdk u32 under _IOP */
typedef signed long        int32_t;    /* == ps2sdk s32 under _IOP */
typedef unsigned long long uint64_t;
typedef signed long long   int64_t;

typedef unsigned long      uintptr_t;
typedef signed long        intptr_t;

#endif
