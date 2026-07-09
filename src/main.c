/*
#     ___  _ _      ___
#    |    | | |    |
# ___|    |   | ___|    PS2DEV Open Source Project.
#----------------------------------------------------------
# (c) 2006-2008 Eugene Plotnikov <e-plotnikov@operamail.com>
# Licenced under Academic Free License version 2.0
# Review ps2sdk README & LICENSE files for further details.
#
*/
#include "SMS_GUI.h"
#include "SMS_CDDA.h"
#include "SMS_CDVD.h"
#include "SMS_EE.h"
#include "SMS_RC.h"
#include "SMS_IOP.h"
#include "SMS_DSP.h"
#include "SMS_DMA.h"
#include "SMS_Locale.h"
#include "SMS_Config.h"
#include "SMS_History.h"
#include "SMS_OS.h"
#include "SMS_GS.h"
#include "SMS_PgInd.h"
#include "SMS_CDDA.h"
#include "SMS_VIF.h"
#include <kernel.h>
#include <sys/ioctl.h>
#include <fileio.h>

#ifdef DISABLE_EXTRA_TIMERS_FUNCTIONS
DISABLE_EXTRA_TIMERS_FUNCTIONS();
#endif

int main ( int argc, char** argv ) {

 int lfFSBoot = 0;

 if ( argc > 0 && argv[ 0 ][ 0 ] == 'm' && argv[ 0 ][ 1 ] == 'c' ) {

  char lSlot = argv[ 0 ][ 2 ];

  SMS_SetMCSlot ( lSlot );
  g_pIPConf   [ 2 ] = lSlot;
  g_pBXDATASYS[ 2 ] = lSlot;
  g_pSMSSkn   [ 2 ] = lSlot;
  g_pSMSRMMAN [ 2 ] = lSlot;
  g_pExec0    [ 2 ] = lSlot;
  g_pExec1    [ 2 ] = lSlot;
  g_MCSlot          = lSlot - '0';

 } else if ( argc > 0 ) {

  SMS_ConfigSetCWD ( argv[ 0 ] );   /* non-mc boot -> settings in CWD ( next to the ELF ) */
  lfFSBoot = 1;

 }  /* end else if */

 SMS_IOPReset ( 0 );
 SMS_EEInit   ();
 CDVD_Init    ();
 CDDA_Init    ();

#ifdef BDM
/* Booted from a filesystem device ( e.g. USB ) -> SMS.cfg lives on that drive,
 * NOT the memory card. Mount USB mass storage NOW, BEFORE GUI_Initialize runs
 * SMS_LoadConfig, otherwise the config read ( and every later save ) targets an
 * unmounted mass0: and silently fails -- the "no settings loaded" + "save
 * errored" seen when booting from USB. Same call AUTO_USB already makes, just
 * earlier; idempotent so SMS_IOPInit's later auto-start is a no-op. Harmless if
 * no USB device is present. */
 if ( lfFSBoot ) SMS_IOPStartUSB ( 0 );
#endif

 GUI_Initialize ( 1 );
 SMS_PgIndStart ();
 GUI_Status ( STR_INITIALIZING_SMS.m_pStr );
#ifndef EMBEDDED
 if ( g_Config.m_BrowserFlags & SMS_BF_UXH ) SMS_OSInit ( argv[ 0 ] );
#endif  /* EMBEDDED */
 SMS_IOPInit     ();
 SMS_EEPort2Init ();
 CDVD_SetSpeed   ();

 if (  CDDA_DiskType () != DiskType_None  ) CDVD_Stop ();

 SMS_LoadXLT ();
 SMS_EEScanDir ( g_pMC0SMS, g_pExtMBF, g_Config.m_pMBFList );
 SMS_HistoryLoad ();
 GUI_DeleteObject ( g_pVerStr );
 SMS_PgIndStop ();

 GUI_Run ();

 return 0;

}  /* end main */
