/*
#     ___  _ _      ___
#    |    | | |    |
# ___|    |   | ___|    PS2DEV Open Source Project.
#----------------------------------------------------------
# (c) 200X... - PS2Dev
# Licenced under Academic Free License version 2.0
# Review ps2sdk README & LICENSE files for further details.
#
*/
#include "SMS_SIF.h"

#include <kernel.h>

int SIF_BindRPC ( SifRpcClientData_t* apData, int anID ) {

 int i, lTry, retVal = 0;

 if ( apData -> server ) return 1;

/* BOUNDED. This was `while ( 1 )`, and the exit conditions do not cover the case that
 * actually happens: SifBindRpc returns >= 0 whenever the CALL is well formed, and
 * apData->server only becomes non-NULL once a server with this id has REGISTERED on the
 * IOP. If that module never loaded, the call keeps succeeding, the server never appears,
 * and this spins forever on the EE.
 *
 * Found on a PSX (DESR-7100), diagnosed by israpps: the DESR BIOS has no rom0:LIBSD --
 * only PLIBSD (XMB) and TLIBSD (testmode) -- so SMS's LIBSD load fails, AUDSRV cannot
 * resolve its imports and never loads, no audio RPC server is ever registered, and
 * SPU_Initialize wedged here. The console looked half-alive: the GUI clock thread kept
 * ticking while the main thread never returned.
 *
 * ~2000 attempts with the existing delay is far more than a server that is coming up needs
 * (the module is already resident by this point in boot; the retry only covers registration
 * lag). Failing returns 0, which every caller already treats as "no server" -- SPU_Initialize
 * simply leaves s_ClientDataA.server NULL and SMS runs without that RPC instead of hanging. */
 for ( lTry = 0; lTry < 2000; ++lTry ) {

  if (  SifBindRpc ( apData, anID, 0 ) < 0  ) break;

  if ( apData -> server ) {

   retVal = 1;
   break;

  }  /* end if */

  i = 10000; while ( i-- );

 }  /* end for */

 return retVal;

}  /* end SIF_BindRPC */
