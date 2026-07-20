/*
#     ___  _ _      ___
#    |    | | |    |
# ___|    |   | ___|    PS2DEV Open Source Project.
#----------------------------------------------------------
# (c) 2005-2009 Eugene Plotnikov <e-plotnikov@operamail.com>
# Licenced under Academic Free License version 2.0
# Review ps2sdk README & LICENSE files for further details.
#
*/
#include "SMS_PgInd.h"
#include "SMS_GS.h"
#include "SMS_EE.h"
#include "SMS_DMA.h"
#include "SMS_Timer.h"

#include <kernel.h>
#include <stdio.h>

#define IND_SIZE 32

extern void* _gp;
extern int   g_XShift;

extern const unsigned char g_IconLoadingRGBA[];  /* 32x32 RGBA, alpha 0..0x80 (SMS_LoadingRGBA.c) */

static int           s_ThreadID;
static int           s_HandlerID;
static unsigned char s_Stack  [                    4096 ] __attribute__(   (  aligned( 16 ), section( ".bss" )  )   );
static u64           s_DrawPkt[                      18 ] __attribute__(   (  aligned( 64 ), section( ".bss" )  )   );
static u64           s_SendPkt[                      24 ] __attribute__(   (  aligned( 64 ), section( ".bss" )  )   );
static unsigned int  s_Bitmap [ IND_SIZE * IND_SIZE * 4 ] __attribute__(   (  aligned( 64 ), section( ".bss" )  )   );

/* Exact cos(2*pi*k/32); sin(k)=cos(k-8)=s_CosTab[(k+24)&31]. */
static const float s_CosTab[ 32 ] __attribute__(   (  aligned( 16 ), section( ".rodata" )  )   ) = {
  1.000000F, 0.980785F, 0.923880F, 0.831470F, 0.707107F, 0.555570F, 0.382683F, 0.195090F,
  0.000000F,-0.195090F,-0.382683F,-0.555570F,-0.707107F,-0.831470F,-0.923880F,-0.980785F,
 -1.000000F,-0.980785F,-0.923880F,-0.831470F,-0.707107F,-0.555570F,-0.382683F,-0.195090F,
  0.000000F, 0.195090F, 0.382683F, 0.555570F, 0.707107F, 0.831470F, 0.923880F, 0.980785F
};

static void _pgind_thread ( void* );

int _vblnk_handler    ( int, void*, void* );
int _vblnk_handler_pg ( int, void*, void* );

void SMS_PgIndInitialize ( void ) {

 if ( !s_ThreadID  ) {

  ee_thread_t lThreadParam;

  lThreadParam.func             = _pgind_thread;
  lThreadParam.stack            = s_Stack;
  lThreadParam.stack_size       = sizeof ( s_Stack );
  lThreadParam.gp_reg           = &_gp;
  lThreadParam.initial_priority = 32;
  s_ThreadID = CreateThread ( &lThreadParam );

 }  /* end if */

}  /* end SMS_PgIndInitialize */

void SMS_PgIndStart ( void ) {

 if ( !s_HandlerID ) {

  int lVMode = GS_Params () -> m_GSCRTMode;

  int ( *lpHandler ) ( int, void*, void* ) = _vblnk_handler_pg;

  if ( lVMode == GSVideoMode_NTSC ||
       lVMode == GSVideoMode_PAL  ||
       lVMode == GSVideoMode_DTV_1920x1080I
  ) lpHandler = _vblnk_handler;

  s_HandlerID = AddIntcHandler2 (  2, lpHandler, 0, ( void* )s_ThreadID  );

  StartThread ( s_ThreadID, NULL );
  EnableIntc ( 2 );

 }  /* end if */

}  /* end SMS_PgIndStart */

void SMS_PgIndStop ( void ) {

 if ( s_HandlerID ) {

  u64*           lpDMA = UNCACHED_SEG( &s_SendPkt[ 18 ] );

  lpDMA[ 0 ] = GIF_TAG( 1, 1, 0, 0, 0, 1 );

  SMS_EEDIntr ();
   if (  RemoveIntcHandler ( 2, s_HandlerID ) <= 0  ) DisableIntc ( 2 );
  SMS_EEIntr ( 1 );

  TerminateThread ( s_ThreadID );

  s_HandlerID = 0;

  DMA_SendChain ( DMAC_GIF, s_SendPkt );
  DMA_Wait ( DMAC_GIF );

 }  /* end if */

}  /* end SMS_PgIndStop */

int _vblnk_handler ( int, void*, void* );
__asm__(
 ".set noreorder\n\t"
 ".set nomacro\n\t"
 ".set noat\n\t"
 ".text\n\t"
 "_vblnk_handler:\n\t"
 "lui       $at, 0x1200\n\t"
 "ld        $at, 0x1000($at)\n\t"
 "dsrl      $at, $at, 13\n\t"
 "andi      $at, $at, 1\n\t"
 "bnel      $at, $zero, 1f\n\t"
 "pcpyld    $ra, $ra, $ra\n\t"
 "2:\n\t"
 "jr        $ra\n\t"
 "xor       $v0, $v0, $v0\n\t"
 "1:\n\t"
 "jal       iWakeupThread\n\t"
 "or        $a0, $zero, $a1\n\t"
 "beq       $zero, $zero, 2b\n\t"
 "pcpyud    $ra, $ra, $ra\n\t"
 ".set at\n\t"
 ".set macro\n\t"
 ".set reorder\n\t"
);

int _vblnk_handler_pg ( int, void*, void* );
__asm__(
 ".set noreorder\n\t"
 ".set nomacro\n\t"
 ".set noat\n\t"
 ".data\n\t"
 "s_Field:  .byte   0\n\t"
 ".text\n\t"
 "_vblnk_handler_pg:\n\t"
 "lui       $a0, %hi( s_Field )\n\t"
 "lbu       $at, %lo( s_Field )($a0)\n\t"
 "nor       $v0, $zero, $at\n\t"
 "bne       $at, $zero, 1f\n\t"
 "sb        $v0, %lo( s_Field )($a0)\n\t"
 "2:\n\t"
 "jr        $ra\n\t"
 "xor       $v0, $v0, $v0\n\t"
 "1:\n\t"
 "pcpyld    $ra, $ra, $ra\n\t"
 "jal       iWakeupThread\n\t"
 "or        $a0, $zero, $a1\n\t"
 "beq       $zero, $zero, 2b\n\t"
 "pcpyud    $ra, $ra, $ra\n\t"
 ".set at\n\t"
 ".set macro\n\t"
 ".set reorder\n\t"
);

static void _pgind_thread ( void* apArg ) {

 static int    s_lIdx = 0;                                   /* frame 0..31, persists across Start/Stop */

 int           lDrawX  = ( g_GSCtx.m_Width  - IND_SIZE ) >> 1;
 int           lDrawY  = ( g_GSCtx.m_Height - IND_SIZE ) >> 1;
 int           lCX     = lDrawX + ( IND_SIZE >> 1 );
 int           lCY     = lDrawY + ( IND_SIZE >> 1 );

/* bg grab/restore region: a 2*IND_SIZE square CENTERED on the icon's rotation centre
 * ( lCX, lCY ). The old top-left ( lDrawX - IND_SIZE, lDrawY - IND_SIZE ) centred the box on
 * ( lDrawX, lDrawY ), i.e. 16px up-left of lCX/lCY, so the box ended at the icon's unrotated
 * right/bottom edge with NO margin. When the 32x32 icon rotates it reaches ~22.6px from the
 * centre ( 16 * sqrt2 ), poking ~7px past the box on the right and bottom -- those pixels were
 * never restored, leaving the "crumbs"/outline smears. Shifting the box right+down by
 * IND_SIZE/2 centres it on lCX/lCY, covering the full rotated extent ( 64 >= 46 ) with margin.
 * Same size, so s_Bitmap / lQWC are unchanged. */
 int           lSendX  = ( lDrawX - ( IND_SIZE >> 1 ) ) >> g_XShift;
 int           lSendY  = lDrawY - ( IND_SIZE >> 1 );
 int           lSendW  = ( IND_SIZE << 1 ) >> g_XShift;
 GSPixelFormat lPSM    = g_GSCtx.m_DrawCtx[ 0 ].m_FRAMEVal.PSM;
 unsigned int  lFBW    = g_GSCtx.m_DrawCtx[ 0 ].m_FRAMEVal.FBW;
 float         lAR     = GS_Params () -> m_AspectRatio[ 0 ];
 int           lPSendY = ( int )( lSendY * lAR );
 int           lPSendH = ( int )(  ( IND_SIZE << 1 ) * lAR  ) + 2;
 int           lQWC    = (   (   lSendW * lPSendH * (  2 + ( lPSM == GSPixelFormat_PSMCT24 )  )   ) + 15    ) >> 4;

 int           lXShift = g_XShift;

 unsigned int  lTBW    = ( IND_SIZE + 63 ) >> 6;             /* = 1 */
 unsigned int  lTexPtr = 0x4000 - (
                (   ( lTBW << 6 ) * (  ( IND_SIZE + 31 ) & ~31  ) * 4   ) >> 8 );   /* = 0x3FE0 */
 unsigned int  lTW = 5, lTH = 5;

 GSStoreImage  lStoreParam;
 GSLoadImage   lLI;
 GSLoadImage*  lpLI = UNCACHED_SEG( &lLI );
 u64           lDMA[ 4 ] __attribute__(   (  aligned( 16 )  )   );

 lDMA[ 0 ] = DMA_TAG(  0, 0, DMATAG_ID_CALL, 0, s_SendPkt, 0 );
 lDMA[ 2 ] = DMA_TAG(  9, 0, DMATAG_ID_REFE, 0, s_DrawPkt, 0 );   /* QWC MUST be 9 */

 s_SendPkt[  0 ] = DMA_TAG( 6, 0, DMATAG_ID_CNT, 0, 0, 0 );
 s_SendPkt[  1 ] = 0L;
 s_SendPkt[  2 ] = GIF_TAG( 4, 0, 0, 0, 0, 1 );
 s_SendPkt[  3 ] = GIFTAG_REGS_AD;
 s_SendPkt[  4 ] = GS_SET_TRXREG( lSendW, lPSendH );
 s_SendPkt[  5 ] = GS_TRXREG;
 s_SendPkt[  6 ] = GS_SET_BITBLTBUF( 0, 0, lPSM, 0, lFBW, lPSM );
 s_SendPkt[  7 ] = GS_BITBLTBUF;
 s_SendPkt[  8 ] = GS_SET_TRXPOS( 0, 0, lSendX, lPSendY, GS_TRXPOS_DIR_LR_UD );
 s_SendPkt[  9 ] = GS_TRXPOS;
 s_SendPkt[ 10 ] = GS_SET_TRXDIR( GS_TRXDIR_HOST_TO_LOCAL );
 s_SendPkt[ 11 ] = GS_TRXDIR;
 s_SendPkt[ 12 ] = GIF_TAG( lQWC, 0, 0, 0, 2, 0 );
 s_SendPkt[ 13 ] = 0L;
 s_SendPkt[ 14 ] = DMA_TAG(  lQWC, 0, DMATAG_ID_REF, 0, ( unsigned int )s_Bitmap, 0  );
 s_SendPkt[ 15 ] = 0L;
 s_SendPkt[ 16 ] = DMA_TAG( 2, 0, DMATAG_ID_RET, 0, 0, 0 );
 s_SendPkt[ 17 ] = 0L;
 s_SendPkt[ 18 ] = GIF_TAG( 1, 0, 0, 0, 0, 1 );
 s_SendPkt[ 19 ] = GIFTAG_REGS_AD;
 s_SendPkt[ 20 ] = GS_SET_TEXFLUSH( 0 );
 s_SendPkt[ 21 ] = GS_TEXFLUSH;

 /* header AD = TEX0 + ALPHA + PRIM (NLOOP 3); then PACKED tristrip of 4 (UV,XYZ).
  * u64 idx: header [0..7], strip tag [8..9], verts [10..17]; per-frame rewrite [11,13,15,17]. */
 s_DrawPkt[ 0 ] = GIF_TAG( 3, 0, 0, 0, 0, 1 );
 s_DrawPkt[ 1 ] = GIFTAG_REGS_AD;
 s_DrawPkt[ 2 ] = GS_SET_TEX0( lTexPtr, lTBW, GSPixelFormat_PSMCT32, lTW, lTH,
                               GS_TEX_TCC_RGBA, GS_TEX_TFX_DECAL, 0, 0, 0, 0, 0 );
 s_DrawPkt[ 3 ] = GS_TEX0_1;
 s_DrawPkt[ 4 ] = GS_SET_ALPHA( GS_ALPHA_A_CS, GS_ALPHA_B_CD, GS_ALPHA_C_AS, GS_ALPHA_D_CD, 0 );
 s_DrawPkt[ 5 ] = GS_ALPHA_1;
 s_DrawPkt[ 6 ] = GS_SET_PRIM( GS_PRIM_PRIM_TRISTRIP, GS_PRIM_IIP_FLAT, GS_PRIM_TME_ON,
                               GS_PRIM_FGE_OFF, GS_PRIM_ABE_ON, GS_PRIM_AA1_OFF,
                               GS_PRIM_FST_UV, GS_PRIM_CTXT_1, GS_PRIM_FIX_UNFIXED );
 s_DrawPkt[ 7 ] = GS_PRIM;
 s_DrawPkt[ 8 ] = GIF_TAG( 4, 1, 0, 0, 1, 2 );   /* FLG=1 REGLIST: the 4 verts below pack UV+XYZ2 two-per-qword ( [10]=UV0 [11]=XYZ0 ... ). FLG=0 PACKED misreads them ( each reg = a full qword ) -> garbage/off-screen quad = invisible spinner. Matches the ball sim's REGLIST vertex tag. */
 s_DrawPkt[ 9 ] = GS_UV | ( GS_XYZ2 << 4 );
 s_DrawPkt[ 10 ] = GS_SET_UV(  0 * 16 + 8,  0 * 16 + 8 );
 s_DrawPkt[ 12 ] = GS_SET_UV( 31 * 16 + 8,  0 * 16 + 8 );
 s_DrawPkt[ 14 ] = GS_SET_UV(  0 * 16 + 8, 31 * 16 + 8 );
 s_DrawPkt[ 16 ] = GS_SET_UV( 31 * 16 + 8, 31 * 16 + 8 );

 GS_InitStoreImage ( &lStoreParam, 0, lSendX, lPSendY, lSendW, lPSendH );
 FlushCache ( 0 );                                          /* also flushes the static s_DrawPkt header for REFE */
 GS_StoreImage ( &lStoreParam, s_Bitmap );

 GS_InitLoadImage ( &lLI, lTexPtr, lTBW, GSPixelFormat_PSMCT32, 0, 0, IND_SIZE, IND_SIZE );
 SyncDCache ( &lLI, &lLI + 1 );
 lpLI -> m_TrxPosReg.m_Value = GS_SET_TRXPOS( 0, 0, 0, 0, 0 );
 GS_LoadImage ( &lLI, ( void* )g_IconLoadingRGBA );
 DMA_Wait ( DMAC_GIF );

 while ( 1 ) {

  float lc, ls;
  u64*  lpDMA = UNCACHED_SEG( &s_DrawPkt[ 0 ] );

  SleepThread ();

  lc = s_CosTab[ s_lIdx ];
  ls = s_CosTab[ ( s_lIdx + 24 ) & 31 ];

  /* rotate offsets, then apply GS_XYZ's exact per-axis transform inline (x:>>xshift<<4, y:*AR<<4). */
  {
   float rx, ry;   int dx, dy;   u64* p = &lpDMA[ 0 ];
   #define PGIND_SET( SLOT, DX, DY )                                                  \
     rx = ( DX ) * lc - ( DY ) * ls;                                                  \
     ry = ( DX ) * ls + ( DY ) * lc;                                                  \
     dx = ( ( lCX + ( int )( rx + ( rx >= 0 ? 0.5F : -0.5F ) ) ) >> lXShift ) << 4;   \
     dy = ( int )( ( lCY + ry ) * lAR + ( ( lCY + ry ) >= 0 ? 0.5F : -0.5F ) ) << 4;  \
     p[ SLOT ] = GS_SET_XYZ( dx, dy, 0 )
   PGIND_SET( 11, -16, -16 );   /* TL */
   PGIND_SET( 13,  16, -16 );   /* TR */
   PGIND_SET( 15, -16,  16 );   /* BL */
   PGIND_SET( 17,  16,  16 );   /* BR */
   #undef PGIND_SET
  }

  s_lIdx = ( s_lIdx + 1 ) & 31;

  DMA_SendChain ( DMAC_GIF, lDMA );

 }  /* end while */

}  /* end _pgind_thread */
