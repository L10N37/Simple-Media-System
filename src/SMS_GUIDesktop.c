/*
#     ___  _ _      ___
#    |    | | |    |
# ___|    |   | ___|    PS2DEV Open Source Project.
#----------------------------------------------------------
# (c) 2006-2007 Eugene Plotnikov <e-plotnikov@operamail.com>
# Licenced under Academic Free License version 2.0
# Review ps2sdk README & LICENSE files for further details.
#
*/
#include "SMS.h"
#include "SMS_GUI.h"
#include "SMS_GS.h"
#include "SMS_DMA.h"
#include "SMS_Timer.h"
#include "SMS_GUIcons.h"
#include "SMS_GUIClock.h"
#include "SMS_Config.h"
#include "SMS_VIF.h"
#include "SMS_PAD.h"
#include "SMS_GUIMenu.h"
#include "SMS_Locale.h"
#include "SMS_IPU.h"
#include "SMS_SPU.h"
#include "SMS_IOP.h"
#include "SMS_Sounds.h"
#include "SMS_MC.h"
#include "SMS_RC.h"
#include "SMS_JPEG.h"
#include "SMS_Rescale.h"

#include <kernel.h>
#include <malloc.h>
#include <stdio.h>
#include <string.h>
#include <libhdd.h>

extern unsigned char jellyfish_jpg[];
extern unsigned int  size_jellyfish_jpg;
extern unsigned char splash_rgba[];   /* 512x512 RGBA boot splash ( bin2c of images/splash.rgba ) */

#define LOGO_W 17
#define LOGO_H  5

extern void About ( void );

static struct {

 int m_X;
 int m_Y;

} s_LogoXY[ 51 ] = {
 {  4, 0 }, {  3, 0 }, {  2, 0 }, {  1, 0 }, {  0, 0 },
 {  0, 1 }, {  0, 2 }, {  1, 2 }, {  2, 2 }, {  3, 2 },
 {  4, 2 }, {  4, 3 }, {  4, 4 }, {  3, 4 }, {  2, 4 },
 {  1, 4 }, {  0, 4 }, {  6, 4 }, {  6, 3 }, {  6, 2 },
 {  6, 1 }, {  6, 0 }, {  7, 0 }, {  8, 0 }, {  8, 1 },
 {  8, 2 }, {  8, 3 }, {  8, 4 }, {  9, 0 }, { 10, 0 },
 { 10, 1 }, { 10, 2 }, { 10, 3 }, { 10, 4 }, { 16, 0 },
 { 15, 0 }, { 14, 0 }, { 13, 0 }, { 12, 0 }, { 12, 1 },
 { 12, 2 }, { 13, 2 }, { 14, 2 }, { 15, 2 }, { 16, 2 },
 { 16, 3 }, { 16, 4 }, { 15, 4 }, { 14, 4 }, { 13, 4 }, { 12, 4 }
};

typedef struct _Version {

 DECLARE_GUI_OBJECT()

} _Version;

static int            s_Init     __attribute__(   (  section( ".data" )  )   ) = 0;
static GSLoadImage    s_BitBltSL;
static void*          s_pSLArea  __attribute__(   (  aligned( 64 )  )   );
static u64*           s_pDMASL;
static unsigned int   s_nDMASL;

static void _Version_Render ( GUIObject* apObj, int aCtx ) {

 if ( !apObj -> m_pGSPacket ) {

  int  lX, lY, lW, lLen;
  char lFmt [ 32 ];
  char lBuff[ 64 ];

  lFmt[  0 ] = 'V';
  lFmt[  1 ] = 'e';
  lFmt[  2 ] = 'r';
  lFmt[  3 ] = 's';
  lFmt[  4 ] = 'i';
  lFmt[  5 ] = 'o';
  lFmt[  6 ] = 'n';
  lFmt[  7 ] = ' ';
  lFmt[  8 ] = '%';
  lFmt[  9 ] = '.';
  lFmt[ 10 ] = '1';
  lFmt[ 11 ] = 'f';
  lFmt[ 12 ] = ' ';
  lFmt[ 13 ] = '(';
  lFmt[ 14 ] = 'R';
  lFmt[ 15 ] = 'e';
  lFmt[ 16 ] = 'v';
  lFmt[ 17 ] = '.';
  lFmt[ 18 ] = '%';
  lFmt[ 19 ] = 'd';
  lFmt[ 20 ] = ')';
  lFmt[ 21 ] = '\x00';
  sprintf ( lBuff, lFmt, 2.9F, 4 );

  lLen = strlen ( lBuff );
  lW   = GSFont_WidthEx ( lBuff, lLen, -6 );
  lX   = (  ( g_GSCtx.m_Width  - LOGO_W * 32 ) >> 1  ) + 32 * LOGO_W - lW;
  lY   = (  ( g_GSCtx.m_Height - LOGO_H * 32 ) >> 1  ) + 32 * s_LogoXY[ 50 ].m_Y + 32;

  apObj -> m_pGSPacket = GSContext_NewList (  GS_TXT_PACKET_SIZE( lLen )  );

  g_GSCtx.m_TextColor = 3;
  GSFont_RenderEx ( lBuff, lLen, lX, lY, apObj -> m_pGSPacket, -6, -12 );

 }  /* end if */

 GSContext_CallList ( aCtx, apObj -> m_pGSPacket );

}  /* end _Version_Render */

GUIObject* GUI_CreateVersion ( void ) {

 _Version* retVal = ( _Version* )calloc (  1, sizeof ( _Version )  );

 retVal -> Render  = _Version_Render;
 retVal -> Cleanup = GUIObject_Cleanup;

 return ( GUIObject* )retVal;

}  /* end GUI_CreateVersion */

extern void PowerOf2 ( int, int, int*, int* );

static int DrawSkin ( void ) {

 int  lFD; 
 int  retVal = 0;
 char lPath[ 128 ];

 strcpy ( lPath, g_pSMSSkn + 5       );
 strcat ( lPath, g_SlashStr          );
 strcat ( lPath, g_Config.m_SkinName );
 strcat ( lPath, g_pSMI              );

 lFD = MC_OpenS ( g_MCSlot, 0, lPath, O_RDONLY );

 if ( lFD >= 0 ) { 

  s64            lSize; 
  unsigned char* lpData; 

  lSize = MC_SeekS ( lFD, 0, SEEK_END ); 
  MC_SeekS ( lFD, 0, SEEK_SET ); 

  lpData = malloc ( lSize ); 

  if ( lpData ) {

   unsigned short lWidth, lHeight;

   MC_ReadS ( lFD, lpData, lSize );

   lWidth = IPU_ImageInfo ( lpData, &lHeight );

   if ( lWidth ) {

    IPULoadImage   lLoadImg;
    u64*           lpDMA;

    g_GSCtx.m_TBW = ( lWidth + 63 ) >> 6;

    g_GSCtx.m_VRAMTexPtr = 0x4000 - (
     (   ( g_GSCtx.m_TBW << 6 ) * (  ( lHeight + 31 ) & ~31  ) * 4   ) >> 8
    );
    PowerOf2 ( lWidth, lHeight, ( int * )&g_GSCtx.m_TW, ( int * )&g_GSCtx.m_TH );

    IPU_InitLoadImage ( &lLoadImg, lWidth, lHeight );
    IPU_LoadImage ( &lLoadImg, lpData, lSize, 0, 0, 0, 0, 0 );

    if ( lLoadImg.m_fPal ) SMS_SetPalette ( lLoadImg.m_Pal );

    lLoadImg.Destroy ( &lLoadImg );

    lpDMA = GSContext_NewPacket (  0, GS_TSP_PACKET_SIZE(), GSPaintMethod_Init  );
    GSContext_RenderTexSprite (
     ( GSTexSpritePacket* )( lpDMA - 2 ),
     0, 0, g_GSCtx.m_Width, g_GSCtx.m_Height, 0, 0, lWidth, lHeight
    );

	if (  GS_Params () -> m_GSCRTMode == GSVideoMode_DTV_1920x1080I  ) {

     lpDMA = GSContext_NewPacket (  0, GS_VGR_PACKET_SIZE(), GSPaintMethod_Continue  );
     GSContext_RenderVGRect (
      lpDMA, g_GSCtx.m_Width, 0, 1920, g_GSCtx.m_Height,
      GS_SET_RGBAQ( 0x00, 0x00, 0x00, 0xFF, 0x00 ),
      GS_SET_RGBAQ( 0x00, 0x00, 0x00, 0xFF, 0x00 )
     );

	}  /* end if */

    GSContext_Flush ( 0, GSFlushMethod_DeleteLists );

    GUI_SetColors ();
    GSFont_Init   ();

    retVal = 1;

   }  /* end if */

   free ( lpData );

  }  /* end if */

  MC_CloseS ( lFD );

 }  /* end if */

 return retVal;

}  /* end DrawSkin */

/* Decoded-once cache for the embedded jellyfish background.        */
/* s_pJFTex holds the image as PSMCT32 (RGBA) ready for GS upload.   */
static unsigned char* s_pJFTex __attribute__(   (  section( ".data" )  )   ) = NULL;
static int            s_JFW    __attribute__(   (  section( ".data" )  )   ) = 0;
static int            s_JFH    __attribute__(   (  section( ".data" )  )   ) = 0;

static int _DecodeJellyfish ( void ) {

 SMS_JPEGContext* lpCtx;
 int              lW, lH, i, lN;
 unsigned char*   lpSrc;
 unsigned char*   lpDst;

 if ( s_pJFTex ) return 1;  /* already decoded & cached */

 lpCtx = SMS_JPEGInit ( NULL, NULL );

 if ( !lpCtx ) return 0;

 if (  SMS_JPEGLoad ( lpCtx, jellyfish_jpg, size_jellyfish_jpg )  ) {

  lW = lpCtx -> m_pRC -> m_NewWidth;
  lH = lpCtx -> m_pRC -> m_NewHeight;

  s_pJFTex = ( unsigned char* )memalign (  64, lW * lH * 4  );

  if ( s_pJFTex ) {
/* expand packed 24-bit RGB -> 32-bit RGBA expected by RenderTexSprite */
   lpSrc = lpCtx -> m_pBitmap;
   lpDst = s_pJFTex;
   lN    = lW * lH;

   for ( i = 0; i < lN; ++i ) {
    lpDst[ 0 ] = lpSrc[ 0 ];
    lpDst[ 1 ] = lpSrc[ 1 ];
    lpDst[ 2 ] = lpSrc[ 2 ];
    lpDst[ 3 ] = 0x80;       /* opaque ( GS uses 0x80 as full alpha ) */
    lpSrc += 3;
    lpDst += 4;
   }  /* end for */

   SyncDCache (  s_pJFTex, s_pJFTex + lW * lH * 4  );

   s_JFW = lW;
   s_JFH = lH;

  }  /* end if */

 }  /* end if */

 SMS_JPEGDestroy ( lpCtx );

 return s_pJFTex != NULL;

}  /* end _DecodeJellyfish */

static int _DrawJellyfish ( void ) {

 int          lY, lBand;
 u64*         lpDMA;
 GSLoadImage  lLI;
 GSLoadImage* lpLI = UNCACHED_SEG( &lLI );

 if (  !_DecodeJellyfish ()  ) return 0;

 g_GSCtx.m_TBW = ( s_JFW + 63 ) >> 6;

 g_GSCtx.m_VRAMTexPtr = 0x4000 - (
  (   ( g_GSCtx.m_TBW << 6 ) * (  ( s_JFH + 31 ) & ~31  ) * 4   ) >> 8
 );
 PowerOf2 ( s_JFW, s_JFH, ( int* )&g_GSCtx.m_TW, ( int* )&g_GSCtx.m_TH );

/* upload the cached texture to VRAM in 32-row bands so each image    */
/* transfer stays within the GIF NLOOP ( 0x7FFF QWC ) limit.          */
 lBand = 32;

 GS_InitLoadImage (
  &lLI, g_GSCtx.m_VRAMTexPtr, g_GSCtx.m_TBW, GSPixelFormat_PSMCT32, 0, 0, s_JFW, lBand
 );
 SyncDCache ( &lLI, &lLI + 1 );

 for ( lY = 0; lY < s_JFH; lY += lBand ) {

  int lRows = ( lY + lBand <= s_JFH ) ? lBand : ( s_JFH - lY );

  if ( lRows != lBand ) {
   GS_InitLoadImage (
    &lLI, g_GSCtx.m_VRAMTexPtr, g_GSCtx.m_TBW, GSPixelFormat_PSMCT32, 0, 0, s_JFW, lRows
   );
   SyncDCache ( &lLI, &lLI + 1 );
  }  /* end if */

  lpLI -> m_TrxPosReg.m_Value = GS_SET_TRXPOS( 0, 0, 0, lY, 0 );
  GS_LoadImage (  &lLI, s_pJFTex + s_JFW * lY * 4  );
  DMA_Wait ( DMAC_GIF );

 }  /* end for */

/* blit full-screen, exactly like DrawSkin does for a skin image */
 lpDMA = GSContext_NewPacket (  0, GS_TSP_PACKET_SIZE(), GSPaintMethod_Init  );
 GSContext_RenderTexSprite (
  ( GSTexSpritePacket* )( lpDMA - 2 ),
  0, 0, g_GSCtx.m_Width, g_GSCtx.m_Height, 0, 0, s_JFW, s_JFH
 );
 GSContext_Flush ( 0, GSFlushMethod_KeepLists );

 return 1;

}  /* end _DrawJellyfish */

/* Boot splash: blit the pre-composited 512x512 opaque RGBA image ( jellyfish +
 * "SMS" sphere logo + authors strip ) full-screen. Same upload/blit path as the
 * jellyfish background -- the image is already RGBA so there is no decode and no
 * runtime alpha blending. Texture is transient at the top of VRAM, reused. */
#define SPLASH_W 512
#define SPLASH_H 512

static void _DrawSplash ( void ) {

 int          lY, lBand;
 u64*         lpDMA;
 GSLoadImage  lLI;
 GSLoadImage* lpLI = UNCACHED_SEG( &lLI );

 SyncDCache (  splash_rgba, splash_rgba + SPLASH_W * SPLASH_H * 4  );

 g_GSCtx.m_TBW = ( SPLASH_W + 63 ) >> 6;

 g_GSCtx.m_VRAMTexPtr = 0x4000 - (
  (   ( g_GSCtx.m_TBW << 6 ) * (  ( SPLASH_H + 31 ) & ~31  ) * 4   ) >> 8
 );
 PowerOf2 ( SPLASH_W, SPLASH_H, ( int* )&g_GSCtx.m_TW, ( int* )&g_GSCtx.m_TH );

 lBand = 32;

 GS_InitLoadImage (
  &lLI, g_GSCtx.m_VRAMTexPtr, g_GSCtx.m_TBW, GSPixelFormat_PSMCT32, 0, 0, SPLASH_W, lBand
 );
 SyncDCache ( &lLI, &lLI + 1 );

 for ( lY = 0; lY < SPLASH_H; lY += lBand ) {

  int lRows = ( lY + lBand <= SPLASH_H ) ? lBand : ( SPLASH_H - lY );

  if ( lRows != lBand ) {
   GS_InitLoadImage (
    &lLI, g_GSCtx.m_VRAMTexPtr, g_GSCtx.m_TBW, GSPixelFormat_PSMCT32, 0, 0, SPLASH_W, lRows
   );
   SyncDCache ( &lLI, &lLI + 1 );
  }  /* end if */

  lpLI -> m_TrxPosReg.m_Value = GS_SET_TRXPOS( 0, 0, 0, lY, 0 );
  GS_LoadImage (  &lLI, ( void* )( splash_rgba + SPLASH_W * lY * 4 )  );
  DMA_Wait ( DMAC_GIF );

 }  /* end for */

 lpDMA = GSContext_NewPacket (  0, GS_TSP_PACKET_SIZE(), GSPaintMethod_Init  );
 GSContext_RenderTexSprite (
  ( GSTexSpritePacket* )( lpDMA - 2 ),
  0, 0, g_GSCtx.m_Width, g_GSCtx.m_Height, 0, 0, SPLASH_W, SPLASH_H
 );
 GSContext_Flush ( 0, GSFlushMethod_KeepLists );

}  /* end _DrawSplash */

static void Desktop_Render ( GUIObject* apObj, int aCtx ) {

 if ( !apObj -> m_pGSPacket ) {

  int            i, lW, lH;
  u64            lXYXY;
  int            lX    = ( g_GSCtx.m_Width  - LOGO_W * 32 ) >> 1;
  int            lY    = ( g_GSCtx.m_Height - LOGO_H * 32 ) >> 1;
  u64*           lpDMA = GSContext_NewPacket (  0, GS_VGR_PACKET_SIZE(), GSPaintMethod_InitClear  );
  GSStoreImage   lSIPkt;

  SMS_SetPalette ( NULL );

  if (   aCtx >= 0 && (  !g_Config.m_SkinName[ 0 ] || !DrawSkin ()  )   ) {

   u64           lBP[ 96 ] __attribute__(   (  aligned( 16 )  )   );

   GUI_LoadIcons ();

/* Boot splash: an opaque full-screen image ( jellyfish + "SMS" sphere logo +
 * authors strip ). Show it, hold ~1.2s, then paint the desktop over it.
 * _DrawSplash issues its own GS packets, so re-arm lpDMA for the gradient. */
   _DrawSplash ();
   SMS_TimerWait ( 1200 );
   lpDMA = GSContext_NewPacket ( 0, GS_VGR_PACKET_SIZE(), GSPaintMethod_InitClear );

/* Base layer: keep the procedural gradient as a fallback. It is */
/* fully covered by the opaque jellyfish image when that decodes. */
   GSContext_RenderVGRect (
    lpDMA, 0, 0, g_GSCtx.m_Width, g_GSCtx.m_Height,
    GS_SET_RGBAQ( 0x00, 0x00, 0x40, 0x80, 0x00 ),
    GS_SET_RGBAQ( 0x00, 0x00, 0x00, 0x80, 0x00 )
   );
   GSContext_Flush ( 0, GSFlushMethod_KeepLists );

/* Replace the gradient background with the embedded jellyfish image. */
   _DrawJellyfish ();

   ( void )lBP;  /* animated "SMS" ball-logo watermark removed -- SMS branding
                  * now appears on the boot splash ( _DrawSplash ) above. */

  } else {

   if ( aCtx < 0 ) aCtx = 0;

   GUI_LoadIcons ();

  }  /* end else */

  apObj -> m_pGSPacket = GSContext_NewList ( 2 );

  GS_InitStoreImage (
   &lSIPkt, 0, 0, 0, g_GSCtx.m_LWidth, g_GSCtx.m_PHeight
  );
  GS_StoreImage ( &lSIPkt, g_GSCtx.m_pDBuf );

  lXYXY = GS_L2P ( 0, g_GSCtx.m_Height - 38, g_GSCtx.m_LWidth, 38 );
  lX = ( lXYXY >>  0 ) & 0xFFFF;
  lY = ( lXYXY >> 16 ) & 0xFFFF;
  lW = ( lXYXY >> 32 ) & 0xFFFF;
  lH = ( lXYXY >> 48 ) & 0xFFFF;
  GS_InitLoadImage (
   UNCACHED_SEG( &s_BitBltSL ), 0, g_GSCtx.m_DrawCtx[ 0 ].m_FRAMEVal.FBW,
   g_GSCtx.m_DrawCtx[ 0 ].m_FRAMEVal.PSM, lX, lY, lW, lH
  );
  s_pSLArea = g_GSCtx.m_pDBuf + g_GSCtx.m_LWidth * lY * g_GSCtx.m_PixSize;

  s_Init = 1;

 }  /* end if */

 GSContext_NewPacket ( aCtx, 0, GSPaintMethod_Init );

}  /* end Desktop_Render */

extern void _adjleft_handler  ( GUIMenu*, int );
extern void _adjright_handler ( GUIMenu*, int );
extern void _adjup_handler    ( GUIMenu*, int );
extern void _adjdown_handler  ( GUIMenu*, int );
extern void _save_handler     ( GUIMenu*, int );
extern void _shutdown_handler ( GUIMenu*, int );
extern void _exit_handler     ( GUIMenu*, int );

static int Desktop_HandleEvent ( GUIObject* apObj, u64           anEvent ) {

 int retVal = GUIHResult_Void;

 if ( anEvent & GUI_MSG_PAD_MASK ) switch ( anEvent & GUI_MSG_PAD_MASK ) {

  case RC_MENU      :
  case SMS_PAD_START: {

   GUI_AddObject (  g_SMSMenuStr, GUI_CreateMenuSMS ()  );
   GUI_Redraw ( GUIRedrawMethod_Redraw );
   SMS_GUIClockRedraw ();

   retVal = GUIHResult_Handled;

  } break;

  case SMS_PAD_SELECT | SMS_PAD_L1      : _adjleft_handler  ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case SMS_PAD_SELECT | SMS_PAD_R1      : _adjright_handler ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case SMS_PAD_SELECT | SMS_PAD_L2      : _adjup_handler    ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case SMS_PAD_SELECT | SMS_PAD_R2      : _adjdown_handler  ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case SMS_PAD_SELECT | SMS_PAD_SQUARE  : _save_handler     ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case SMS_PAD_SELECT | SMS_PAD_TRIANGLE: _exit_handler     ( NULL, 1 ); retVal = GUIHResult_Handled; break;
  case RC_RESET                         :
  case SMS_PAD_SELECT | SMS_PAD_CIRCLE  :
   g_Config.m_BrowserFlags &= ~SMS_BF_EXIT;
   _shutdown_handler ( NULL, 1 ); retVal = GUIHResult_Handled;
  break;

  case RC_A_B                                           :
  case SMS_PAD_R1 | SMS_PAD_L1 | SMS_PAD_R2 | SMS_PAD_L2: About (); retVal = GUIHResult_Handled; break;

  case RC_ON: SMS_IOPowerOff ();

 }  /* end switch */

 return retVal;

}  /* end Desktop_HandleEvent */

GUIObject* GUI_CreateDesktop ( void ) {

 GUIObject* retVal = ( GUIObject* )calloc (  1, sizeof ( GUIObject )  );

 retVal -> Render      = Desktop_Render;
 retVal -> HandleEvent = Desktop_HandleEvent;
 retVal -> Cleanup     = GUIObject_Cleanup;

 return retVal;

}  /* end GUI_CreateDesktop */

static void StatusLine_Render ( GUIObject* apObj, int aCtx ) {

 u64*          * lppList = ( u64*          * )&apObj[ 1 ];

 if ( !apObj -> m_pGSPacket ) {

  u64*           lpDMA  = GSContext_NewList (  GS_RRT_PACKET_SIZE()  );
  u64*           lpDMA2 = GSContext_NewList ( 6 );
  unsigned int   lX, lY;

  lX = g_GSCtx.m_Width  - 88;
  lY = g_GSCtx.m_Height - 36;

  GS_RenderRoundRect (
   ( GSRoundRectPacket* )( lpDMA - 2 ),
   0, lY, g_GSCtx.m_Width - 1, 34, -12,
   g_Palette[ g_Config.m_BrowserIBCIdx - 1 ]
  );

  lpDMA2[ 0 ] = GIF_TAG( 1, 1, 0, 0, GIFTAG_FLG_REGLIST, 4 );
  lpDMA2[ 1 ] = GIFTAG_REGS_PRIM | ( GIFTAG_REGS_XYZ2 << 4 ) | ( GIFTAG_REGS_XYZ2 << 8 ) | ( GIFTAG_REGS_NOP << 12 );
  lpDMA2[ 2 ] = GS_SET_PRIM( GS_PRIM_PRIM_LINE, 0, 0, 0, 1, 1, 0, 0, 0 );
  lpDMA2[ 3 ] = GS_XYZ( lX,                   lY, 0 );
  lpDMA2[ 4 ] = GS_XYZ( lX, g_GSCtx.m_Height - 1, 0 );
  lpDMA2[ 5 ] = 0UL;

  apObj -> m_pGSPacket = lpDMA;
  lppList[ 0 ]         = lpDMA2;

  *( int* )UNCACHED_SEG(  ( char* )&s_BitBltSL + 132  ) = ( int )s_pSLArea;

 }  /* end if */

 GSContext_CallList2 (  aCtx, ( u64*           )&s_BitBltSL  );
 GSContext_CallList ( aCtx, apObj -> m_pGSPacket );
 GSContext_CallList ( aCtx, lppList[ 0 ] );

 if ( s_pDMASL ) GSContext_CallList ( aCtx, s_pDMASL + 2 );

}  /* end StatusLine_Render */

static void StatusLine_Cleanup ( GUIObject* apObj ) {

 u64*          * lppList = ( u64*          * )&apObj[ 1 ];

 GUIObject_Cleanup ( apObj );
 GSContext_DeleteList ( lppList[ 0 ] );

 lppList[ 0 ] = 0;

 free ( s_pDMASL );

 s_pDMASL = NULL;
 s_nDMASL = 0;

}  /* end StatusLine_Cleanup */

GUIObject* GUI_CreateStatusLine ( void ) {

 GUIObject* retVal = ( GUIObject* )calloc (  1, sizeof ( GUIObject ) + sizeof ( u64*           )  );

 retVal -> Render  = StatusLine_Render;
 retVal -> Cleanup = StatusLine_Cleanup;

 return retVal;

}  /* end GUI_CreateStatusLine */

void GUI_Status ( char* apMsg ) {

 int lLen   = strlen ( apMsg );
 int lWidth = g_GSCtx.m_Width - 96;
 int lDX    = -2;
 int lQWC;
 unsigned int lWidthOld;

 while (  GSFont_WidthEx ( apMsg, lLen, lDX ) > lWidth && lDX >= -12  ) --lDX;
 while (  GSFont_WidthEx ( apMsg, lLen, lDX ) > lWidth                ) --lLen;

 lWidth  = GS_TXT_PACKET_SIZE( lLen );
 lQWC    = lWidth >> 1;
 lWidth += 2;

 DMA_Wait ( DMAC_VIF1 );

 if ( s_nDMASL < lWidth ) {

  lWidthOld = s_nDMASL * sizeof ( u64           );
  s_pDMASL = ( u64*           )SMS_ReallocWithAlign(  s_pDMASL, &lWidthOld, lWidth * sizeof ( u64           )  );
  s_nDMASL = lWidth;

 }  /* end if */

 g_GSCtx.m_TextColor = 0;

 s_pDMASL[ 0 ] = 0;
 s_pDMASL[ 1 ] = VIF_DIRECT( lQWC );
 GSFont_RenderEx ( apMsg, lLen, 8, g_GSCtx.m_Height - 34, s_pDMASL + 2, lDX, -2 );
 SyncDCache ( s_pDMASL, s_pDMASL + lWidth );

 GSContext_NewPacket ( 1, 0, GSPaintMethod_Init );
 g_pStatusLine -> Render ( g_pStatusLine, 1 );
 SMS_GUIClockSuspend ();
 GSContext_Flush ( 1, GSFlushMethod_KeepLists );
 SMS_GUIClockResume ();

}  /* end GUI_Status */

static int _wait_user ( char* apMsg, int anIcon, int anBtn, unsigned int* apBtn ) {

 int            lLen   = strlen ( apMsg );
 int            lWidth = g_GSCtx.m_Width - 128;
 int            lDX    = -2;
 u64*           lpDMA;
 u64            lIcon[ 32 ] __attribute__(   (  aligned( 16 )  )   );

 while (   GSFont_WidthEx ( apMsg, lLen, lDX ) > lWidth && lDX >= -12  ) --lDX;
 while (   GSFont_WidthEx ( apMsg, lLen, lDX ) > lWidth                ) --lLen;

 g_GSCtx.m_TextColor = 0;
 GSContext_NewPacket (  1, 0, GSPaintMethod_Init  );
 GSContext_CallList2 (  1, ( u64*           )&s_BitBltSL  );
 lpDMA = GSContext_NewPacket (  1, GS_TXT_PACKET_SIZE( lLen ), GSPaintMethod_Continue  );
 GSFont_RenderEx ( apMsg, lLen, 40, lWidth = g_GSCtx.m_Height - 34, lpDMA, lDX, -2 );
 GUI_DrawIcon ( anIcon, 8, lWidth, GUIcon_Misc, lIcon );
 SyncDCache ( &lIcon[ 0 ], &lIcon[ 32 ] );
 lpDMA = (  ( u64*          * )&g_pStatusLine[ 1 ]  )[ 0 ];
 GSContext_CallList2 ( 1, lIcon );
 GSContext_CallList  ( 1, g_pStatusLine -> m_pGSPacket );
 GSContext_CallList  ( 1, lpDMA );
 GSContext_Flush ( 1, GSFlushMethod_KeepLists );
 SPU_PlaySound ( SMSound_Error, g_Config.m_PlayerVolume );
 SMS_GUIClockStop ();
 SMS_GUIClockStart ( &g_Clock );
 lLen = GUI_WaitButtons ( anBtn, apBtn, 200 );
 GSContext_NewPacket (  1, 0, GSPaintMethod_Init  );
 SMS_GUIClockSuspend ();
 g_pStatusLine -> Render ( g_pStatusLine, 1 );
 GSContext_Flush ( 1, GSFlushMethod_KeepLists );
 SMS_GUIClockResume ();

 return lLen;

}  /* end _wait_user */

void GUI_Error ( char* apMsg ) {

 unsigned int lBtn[ 2 ] = { SMS_PAD_CROSS, RC_ENTER };

 _wait_user ( apMsg, GUICON_ERROR, 2, lBtn );

}  /* end GUI_Error */

int GUI_Question ( char* apMsg ) {

 unsigned int lBtn[ 4 ] = {
  SMS_PAD_CROSS, SMS_PAD_TRIANGLE, RC_ENTER, RC_RETURN
 };

 int retVal = _wait_user ( apMsg, GUICON_HELP, 4, lBtn );

 return retVal == SMS_PAD_CROSS || retVal == RC_ENTER;

}  /* end GUI_Question */

void GUI_Progress ( char* apStr, int aPos, int afForceUpdate ) {

 static u64*           s_lpListTxt;
 static u64*           s_lpListRRT;
 static int            s_lLen;
 static int            s_lPos;

 if ( afForceUpdate ) {

  s_lLen = -1;
  s_lPos = -1;

 }  /* end if */

 if ( apStr ) {

  int lLen   = strlen ( apStr );
  int lWidth = g_GSCtx.m_Width - 16;

  while (   GSFont_WidthEx ( apStr, lLen, -2 ) > lWidth  ) --lLen;

  if ( !s_lpListRRT ) s_lpListRRT = GSContext_NewList (  GS_RRT_PACKET_SIZE()  );

  if ( s_lLen != lLen ) {

   GSContext_DeleteList ( s_lpListTxt );
   s_lpListTxt = GSContext_NewList (  GS_TXT_PACKET_SIZE( s_lLen = lLen )  );

   g_GSCtx.m_TextColor = 0;
   GSFont_RenderEx ( apStr, lLen, 8, g_GSCtx.m_Height - 34, s_lpListTxt, -2, -2 );

  }  /* end if */

  if ( aPos < 2 )

   aPos = 2;

  else if ( aPos > 100 ) aPos = 100;

  if ( s_lPos != aPos ) {

   lWidth = (  ( g_GSCtx.m_Width - 4 ) * aPos  ) / 100;
   s_lPos = aPos;

   GS_RenderRoundRect (
    ( GSRoundRectPacket* )( s_lpListRRT - 2 ), 4, g_GSCtx.m_Height - 35, lWidth - 4, 34, 12, 0x20FF8080
   );

   GSContext_NewPacket (  1, 0, GSPaintMethod_Init          );
   GSContext_CallList2 (  1, ( u64*           )&s_BitBltSL  );
   GSContext_CallList  (  1, g_pStatusLine -> m_pGSPacket   );
   GSContext_CallList  (  1, s_lpListRRT                    );
   GSContext_CallList  (  1, s_lpListTxt                    );
   GSContext_Flush     (  1, GSFlushMethod_KeepLists        );

  }  /* end if */

 } else {

  GSContext_NewPacket (  1, 0, GSPaintMethod_Init          );
  GSContext_CallList2 (  1, ( u64*           )&s_BitBltSL  );
  GSContext_CallList  (  1, g_pStatusLine -> m_pGSPacket   );
  GSContext_Flush     (  1, GSFlushMethod_KeepLists        );

  GSContext_DeleteList ( s_lpListRRT );
  GSContext_DeleteList ( s_lpListTxt );

  s_lpListRRT = NULL;
  s_lpListTxt = NULL;

 }  /* end else */

}  /* end GUI_Progress */
