/*
#     ___  _ _      ___
#    |    | | |    |
# ___|    |   | ___|    PS2DEV Open Source Project.
#----------------------------------------------------------
# (c) 2007 Eugene Plotnikov <e-plotnikov@operamail.com>
# Licenced under Academic Free License version 2.0
# Review ps2sdk README & LICENSE files for further details.
#
*/
#include "SMS_GUIMenu.h"
#include "SMS_Config.h"
#include "SMS_Locale.h"
#include "SMS_FileDir.h"
#include "SMS_IOP.h"
#include "SMS_GUIcons.h"
#include "SMS_PgInd.h"

#include <malloc.h>
#include <string.h>
#include <fileio.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct SMBInfo {

 SMString     m_Title;
 GUIMenuItem* m_pItems;
 SMString*    m_pStrings;
 int          m_CurIdx;

} SMBInfo;

extern void GUIMenuSMS_UpdateStatus ( GUIMenu*                  );
extern int  GUIMenuSMS_HandleEvent  ( GUIObject*, u64           );

static int GUIMenuSMB_HandleEvent ( GUIObject* apObj, u64           anEvent ) {

 return GUIMenuSMS_HandleEvent ( apObj, anEvent );

}  /* end GUIMenuSMB_HandleEvent */

static void _user_data_destructor ( void* apArg ) {

 SMBInfo* lpInfo = ( SMBInfo* )apArg;

 free ( lpInfo -> m_Title.m_pStr );
 free ( lpInfo -> m_pItems       );
 free ( lpInfo -> m_pStrings     );

}  /* end _user_data_destructor */

/* ----------------------------------------------------------------------------
 * In-GUI SMB server configuration (add / edit / delete + writer).
 * Lets the user create SMS.smb entries from scratch, with no hand-made file.
 * ------------------------------------------------------------------------- */

extern void SMS_SaveSMBInfo ( void );

void        _smb_menu   ( GUIMenu* apMenu );
static void _smb_reopen ( GUIMenu* apMenu );

static char s_pAddServer  [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Add server...";
static char s_pEditServer [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Edit server...";
static char s_pServerName [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Server name";
static char s_pUserName   [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Username";
static char s_pPassword   [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Password";
static char s_pClientName [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Client name";
static char s_pEditTitle  [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "SMB server";
static char s_pPickTitle  [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Edit text";
static char s_pDone       [] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) = "Done";

static SMString s_StrAddServer  __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pAddServer  ) - 1, s_pAddServer  };
static SMString s_StrEditServer __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pEditServer ) - 1, s_pEditServer };
static SMString s_StrServerName __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pServerName ) - 1, s_pServerName };
static SMString s_StrUserName   __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pUserName   ) - 1, s_pUserName   };
static SMString s_StrPassword   __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pPassword   ) - 1, s_pPassword   };
static SMString s_StrClientName __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pClientName ) - 1, s_pClientName };
static SMString s_StrEditTitle  __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pEditTitle  ) - 1, s_pEditTitle  };
static SMString s_StrPickTitle  __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pPickTitle  ) - 1, s_pPickTitle  };
static SMString s_StrDone       __attribute__(   (  section( ".data" )  )   ) = { sizeof ( s_pDone       ) - 1, s_pDone       };

/* charset cycled by the per-character picker spinners */
static char s_pPickChars[] __attribute__(   (  section( ".data" ), aligned( 1 )  )   ) =
 " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-";

/* working copy of the record being added / edited */
static SMBLoginInfo s_AddInfo  __attribute__(   (  section( ".bss" )  )   );
static char         s_AddIP[ 4 ][ 4 ] __attribute__(   (  section( ".bss" )  )   );
static char         s_AddDescr[ 64 ]  __attribute__(   (  section( ".bss" )  )   );

static SMS_ListNode* s_pEditNode __attribute__(   (  section( ".bss" )  )   );

/* SMString views for the form's right-hand value column */
static SMString s_StrAddIP  [ 4 ] __attribute__(   (  section( ".data" )  )   ) = {
 { 0, s_AddIP[ 0 ] }, { 0, s_AddIP[ 1 ] }, { 0, s_AddIP[ 2 ] }, { 0, s_AddIP[ 3 ] }
};
static SMString s_StrValName   __attribute__(   (  section( ".data" )  )   ) = { 0, s_AddInfo.m_ServerName };
static SMString s_StrValUser   __attribute__(   (  section( ".data" )  )   ) = { 0, s_AddInfo.m_UserName   };
static SMString s_StrValPass   __attribute__(   (  section( ".data" )  )   ) = { 0, s_AddInfo.m_Password   };
static SMString s_StrValClient __attribute__(   (  section( ".data" )  )   ) = { 0, s_AddInfo.m_ClientName };

/* ---- character picker ---- */

#define SMB_PICK_MAX 32

static char*     s_pPickTarget  __attribute__(   (  section( ".bss" )  )   );  /* buffer being edited      */
static int       s_PickLen      __attribute__(   (  section( ".bss" )  )   );  /* number of slots shown    */
static SMString* s_pPickValStr  __attribute__(   (  section( ".bss" )  )   );  /* form item view to refresh */

static char        s_PickSlot   [ SMB_PICK_MAX     ] __attribute__(   (  section( ".bss" )  )   );  /* one char per slot       */
static char        s_PickSlotStr[ SMB_PICK_MAX ][ 2 ] __attribute__(   (  section( ".bss" )  )   );  /* displayable char + NUL  */
static SMString    s_PickSlotSMS[ SMB_PICK_MAX     ] __attribute__(   (  section( ".data" )  )   );
static GUIMenuItem s_PickMenu   [ SMB_PICK_MAX + 1 ] __attribute__(   (  section( ".data" )  )   );

static int _smb_char_index ( char aChar ) {

 const char* lpPos = strchr ( s_pPickChars, aChar );

 if ( lpPos ) return lpPos - s_pPickChars;

 return 0;

}  /* end _smb_char_index */

static void _smb_pick_slot_handler ( GUIMenu* apMenu, int aDir ) {

 GUIMenuState* lpState = (  ( GUIMenuState* )( unsigned int )apMenu -> m_pState -> m_pTail -> m_Param  );
 int           lSlot   = lpState -> m_pCurr - s_PickMenu;
 int           lIdx;
 int           lLast   = strlen ( s_pPickChars ) - 1;

 if ( lSlot < 0 || lSlot >= s_PickLen ) return;

 lIdx = _smb_char_index ( s_PickSlot[ lSlot ] ) + aDir;

 if ( lIdx < 0 )
  lIdx = lLast;
 else if ( lIdx > lLast ) lIdx = 0;

 s_PickSlot[ lSlot ] = s_pPickChars[ lIdx ];

 s_PickSlotStr[ lSlot ][ 0 ] = s_PickSlot[ lSlot ];
 s_PickSlotStr[ lSlot ][ 1 ] = '\x00';
 s_PickSlotSMS[ lSlot ].m_Len = 1;

 apMenu -> Redraw ( apMenu );

}  /* end _smb_pick_slot_handler */

static void _smb_pick_done_handler ( GUIMenu* apMenu, int aDir ) {

 int i, lEnd;

 for ( i = 0; i < s_PickLen; ++i ) s_pPickTarget[ i ] = s_PickSlot[ i ];

 s_pPickTarget[ s_PickLen ] = '\x00';

 for ( lEnd = ( int )strlen ( s_pPickTarget ); lEnd > 0 && s_pPickTarget[ lEnd - 1 ] == ' '; --lEnd )
  s_pPickTarget[ lEnd - 1 ] = '\x00';

 if ( s_pPickValStr ) s_pPickValStr -> m_Len = strlen ( s_pPickTarget );

 GUI_MenuPopState ( apMenu );

 GUIMenuSMS_UpdateStatus ( apMenu );
 apMenu -> Redraw ( apMenu );

}  /* end _smb_pick_done_handler */

/* aMax = full capacity of the buffer (including NUL) */
static void _smb_pick_open ( GUIMenu* apMenu, char* apTarget, int aMax, SMString* apValStr ) {

 int           i;
 GUIMenuState* lpState;
 int           lLen = aMax - 1;

 if ( lLen > SMB_PICK_MAX ) lLen = SMB_PICK_MAX;

 s_pPickTarget = apTarget;
 s_PickLen     = lLen;
 s_pPickValStr = apValStr;

 for ( i = 0; i < lLen; ++i ) {

  s_PickSlot[ i ] = ( i < ( int )strlen ( apTarget ) && apTarget[ i ] ) ? apTarget[ i ] : ' ';

  s_PickSlotStr[ i ][ 0 ] = s_PickSlot[ i ];
  s_PickSlotStr[ i ][ 1 ] = '\x00';

  s_PickSlotSMS[ i ].m_Len = 1;
  s_PickSlotSMS[ i ].m_pStr = s_PickSlotStr[ i ];

  s_PickMenu[ i ].m_Type        = MENU_ITEM_TYPE_TEXT;
  s_PickMenu[ i ].m_pOptionName = &s_PickSlotSMS[ i ];
  s_PickMenu[ i ].m_IconLeft    = 0;
  s_PickMenu[ i ].m_IconRight   = ( unsigned int )&s_PickSlotSMS[ i ];
  s_PickMenu[ i ].Handler       = _smb_pick_slot_handler;
  s_PickMenu[ i ].Enter         = NULL;
  s_PickMenu[ i ].Leave         = NULL;

 }  /* end for */

 s_PickMenu[ lLen ].m_Type        = 0;
 s_PickMenu[ lLen ].m_pOptionName = &s_StrDone;
 s_PickMenu[ lLen ].m_IconLeft    = 0;
 s_PickMenu[ lLen ].m_IconRight   = GUICON_FINISH;
 s_PickMenu[ lLen ].Handler       = _smb_pick_done_handler;
 s_PickMenu[ lLen ].Enter         = NULL;
 s_PickMenu[ lLen ].Leave         = NULL;

 lpState = GUI_MenuPushState ( apMenu );

 lpState -> m_pItems =
 lpState -> m_pFirst =
 lpState -> m_pCurr  = s_PickMenu;
 lpState -> m_pLast  = &s_PickMenu[ lLen ];
 lpState -> m_pTitle = &s_StrPickTitle;

 GUIMenuSMS_UpdateStatus ( apMenu );
 apMenu -> Redraw ( apMenu );

}  /* end _smb_pick_open */

/* ---- add / edit form ---- */

static void _addip_roll ( GUIMenu* apMenu, int aOctet, int aDir ) {

 int lNum = atoi ( s_AddIP[ aOctet ] );

 lNum += aDir;

 if ( lNum < 0 )
  lNum = 255;
 else if ( lNum > 255 ) lNum = 0;

 sprintf ( s_AddIP[ aOctet ], "%d", lNum );

 s_StrAddIP[ aOctet ].m_Len = strlen ( s_AddIP[ aOctet ] );

 apMenu -> Redraw ( apMenu );

}  /* end _addip_roll */

static void _addip1_handler ( GUIMenu* apMenu, int aDir ) { _addip_roll ( apMenu, 0, aDir ); }
static void _addip2_handler ( GUIMenu* apMenu, int aDir ) { _addip_roll ( apMenu, 1, aDir ); }
static void _addip3_handler ( GUIMenu* apMenu, int aDir ) { _addip_roll ( apMenu, 2, aDir ); }
static void _addip4_handler ( GUIMenu* apMenu, int aDir ) { _addip_roll ( apMenu, 3, aDir ); }

static void _addname_handler ( GUIMenu* apMenu, int aDir ) {

 _smb_pick_open (  apMenu, s_AddInfo.m_ServerName, sizeof ( s_AddInfo.m_ServerName ), &s_StrValName  );

}  /* end _addname_handler */

static void _adduser_handler ( GUIMenu* apMenu, int aDir ) {

 _smb_pick_open (  apMenu, s_AddInfo.m_UserName, sizeof ( s_AddInfo.m_UserName ), &s_StrValUser  );

}  /* end _adduser_handler */

static void _addpass_handler ( GUIMenu* apMenu, int aDir ) {

 _smb_pick_open (  apMenu, s_AddInfo.m_Password, sizeof ( s_AddInfo.m_Password ), &s_StrValPass  );

}  /* end _addpass_handler */

static void _addclient_handler ( GUIMenu* apMenu, int aDir ) {

 _smb_pick_open (  apMenu, s_AddInfo.m_ClientName, sizeof ( s_AddInfo.m_ClientName ), &s_StrValClient  );

}  /* end _addclient_handler */

static void _addsave_handler ( GUIMenu* apMenu, int aDir ) {

 SMBLoginInfo* lpInfo;
 char          lIP[ 16 ];

 sprintf (
  lIP, "%s.%s.%s.%s", s_AddIP[ 0 ], s_AddIP[ 1 ], s_AddIP[ 2 ], s_AddIP[ 3 ]
 );

 if (  !s_AddInfo.m_ServerName[ 0 ]  ) {

  GUI_Error ( STR_ERROR.m_pStr );
  return;

 }  /* end if */

 strcpy ( s_AddInfo.m_ServerIP, lIP );

 if (  !s_AddInfo.m_ClientName[ 0 ]  ) strcpy ( s_AddInfo.m_ClientName, "PS2" );

 strupr ( s_AddInfo.m_ServerName );

 s_AddInfo.m_fAsync = 1;

 if ( s_AddDescr[ 0 ] == '\x00' ) strcpy ( s_AddDescr, s_AddInfo.m_ServerName );

 if ( !g_Config.m_pSMBList ) g_Config.m_pSMBList = SMS_ListInit ();

 if ( s_pEditNode ) {

  lpInfo = ( SMBLoginInfo* )( unsigned int )s_pEditNode -> m_Param;

  memcpy (  lpInfo, &s_AddInfo, sizeof ( SMBLoginInfo )  );

  SMS_ListRemove ( g_Config.m_pSMBList, s_pEditNode );

  SMS_ListPushBack ( g_Config.m_pSMBList, s_AddDescr ) -> m_Param = ( unsigned int )lpInfo;

 } else {

  lpInfo = ( SMBLoginInfo* )malloc (  sizeof ( SMBLoginInfo )  );

  memcpy (  lpInfo, &s_AddInfo, sizeof ( SMBLoginInfo )  );

  SMS_ListPushBack ( g_Config.m_pSMBList, s_AddDescr ) -> m_Param = ( unsigned int )lpInfo;

 }  /* end else */

 g_IOPFlags              |= SMS_IOPF_SMBINFO;
 g_Config.m_NetworkFlags |= SMS_DF_SMB;

 SMS_SaveSMBInfo ();

 GUI_MenuPopState ( apMenu );  /* leave the form         */
 _smb_reopen     ( apMenu );  /* rebuild the server list */

}  /* end _addsave_handler */

static GUIMenuItem s_AddMenu[ 10 ] __attribute__(   (  section( ".data" )  )   ) = {
 { MENU_ITEM_TYPE_TEXT, &STR_PS2_IP1,      0, 0, _addip1_handler,   0, 0 },
 { MENU_ITEM_TYPE_TEXT, &STR_PS2_IP2,      0, 0, _addip2_handler,   0, 0 },
 { MENU_ITEM_TYPE_TEXT, &STR_PS2_IP3,      0, 0, _addip3_handler,   0, 0 },
 { MENU_ITEM_TYPE_TEXT, &STR_PS2_IP4,      0, 0, _addip4_handler,   0, 0 },
 { MENU_ITEM_TYPE_TEXT, &s_StrServerName,  0, 0, _addname_handler,  0, 0 },
 { MENU_ITEM_TYPE_TEXT, &s_StrUserName,    0, 0, _adduser_handler,  0, 0 },
 { MENU_ITEM_TYPE_TEXT, &s_StrPassword,    0, 0, _addpass_handler,  0, 0 },
 { MENU_ITEM_TYPE_TEXT, &s_StrClientName,  0, 0, _addclient_handler,0, 0 },
 { 0,                   &STR_SAVE_SETTINGS,0, 0, _addsave_handler,  0, 0 }
};

static void _smb_addedit_form ( GUIMenu* apMenu, SMS_ListNode* apNode ) {

 int           i;
 GUIMenuState* lpState;

 s_pEditNode = apNode;

 memset (  &s_AddInfo, 0, sizeof ( SMBLoginInfo )  );
 s_AddDescr[ 0 ] = '\x00';

 if ( apNode ) {

  SMBLoginInfo* lpSrc = ( SMBLoginInfo* )( unsigned int )apNode -> m_Param;

  memcpy (  &s_AddInfo, lpSrc, sizeof ( SMBLoginInfo )  );

  strncpy (  s_AddDescr, _STR( apNode ), sizeof ( s_AddDescr ) - 1  );

  i = sscanf (
   lpSrc -> m_ServerIP, "%3[^.].%3[^.].%3[^.].%3s",
   s_AddIP[ 0 ], s_AddIP[ 1 ], s_AddIP[ 2 ], s_AddIP[ 3 ]
  );

  if ( i != 4 ) {
   strcpy ( s_AddIP[ 0 ], "0" );
   strcpy ( s_AddIP[ 1 ], "0" );
   strcpy ( s_AddIP[ 2 ], "0" );
   strcpy ( s_AddIP[ 3 ], "0" );
  }  /* end if */

 } else {

  strcpy ( s_AddInfo.m_ClientName, "PS2" );

  strcpy ( s_AddIP[ 0 ], "192" );
  strcpy ( s_AddIP[ 1 ], "168" );
  strcpy ( s_AddIP[ 2 ], "0"   );
  strcpy ( s_AddIP[ 3 ], "1"   );

 }  /* end else */

 for ( i = 0; i < 4; ++i ) s_StrAddIP[ i ].m_Len = strlen ( s_AddIP[ i ] );

 s_StrValName.m_Len   = strlen ( s_AddInfo.m_ServerName );
 s_StrValUser.m_Len   = strlen ( s_AddInfo.m_UserName   );
 s_StrValPass.m_Len   = strlen ( s_AddInfo.m_Password   );
 s_StrValClient.m_Len = strlen ( s_AddInfo.m_ClientName );

 for ( i = 0; i < 4; ++i ) s_AddMenu[ i ].m_IconRight = ( unsigned int )&s_StrAddIP[ i ];

 s_AddMenu[ 4 ].m_IconRight = ( unsigned int )&s_StrValName;
 s_AddMenu[ 5 ].m_IconRight = ( unsigned int )&s_StrValUser;
 s_AddMenu[ 6 ].m_IconRight = ( unsigned int )&s_StrValPass;
 s_AddMenu[ 7 ].m_IconRight = ( unsigned int )&s_StrValClient;
 s_AddMenu[ 8 ].m_IconRight = GUICON_SAVE;

 lpState = GUI_MenuPushState ( apMenu );

 lpState -> m_pItems =
 lpState -> m_pFirst =
 lpState -> m_pCurr  = s_AddMenu;
 lpState -> m_pLast  = &s_AddMenu[ 8 ];
 lpState -> m_pTitle = &s_StrEditTitle;

 GUIMenuSMS_UpdateStatus ( apMenu );
 apMenu -> Redraw ( apMenu );

}  /* end _smb_addedit_form */

static void _smb_handler ( GUIMenu* apMenu, int aDir ) {

 GUIMenuState* lpState = (  ( GUIMenuState* )( unsigned int )apMenu -> m_pState -> m_pTail -> m_Param  );
 SMS_ListNode* lpNode  = SMS_ListFind ( g_Config.m_pSMBList, lpState -> m_pCurr -> m_pOptionName -> m_pStr );
 SMBLoginInfo* lpInfo  = ( SMBLoginInfo* )( unsigned int )lpNode -> m_Param;

 if (  strcmp ( lpInfo -> m_ServerIP, g_Config.m_SMBIP )  ) {

  SMBInfo* lpMenuInfo = ( SMBInfo* )lpState -> m_pUserData;

  lpMenuInfo -> m_pItems[ lpMenuInfo -> m_CurIdx ].m_IconRight = 0;
  lpState -> m_pCurr -> m_IconRight = GUICON_ON;
  lpMenuInfo -> m_CurIdx            = lpState -> m_pCurr - lpMenuInfo -> m_pItems;

  strcpy ( g_Config.m_SMBIP, lpInfo -> m_ServerIP );

  if ( g_IOPFlags & SMS_IOPF_NET_UP ) {

   int lFD = fioDopen ( g_pSMBS );

   if ( lFD >= 0 ) {

    if ( g_IOPFlags & SMS_IOPF_SMBLOGIN ) {
redo:
     fioIoctl ( lFD, SMB_IOCTL_LOGOUT, &g_SMBUnit );
     g_SMBU      = 0x80000000;
     g_IOPFlags &= ~SMS_IOPF_SMBLOGIN;
     GUI_PostMessage ( GUI_MSG_SMB );

    } else {

     int lSts;

     GUI_Status ( STR_SMB_CLOSING.m_pStr );
     SMS_PgIndStart ();
      lSts = fioIoctl ( lFD, SMB_IOCTL_STOPC, &g_SMBUnit );
     SMS_PgIndStop ();
     if ( lSts < 0 ) goto redo;

     GUI_PostMessage ( GUI_MSG_MOUNT_BIT | GUI_MSG_LOGIN );

    }  /* end else */

    fioDclose ( lFD );
    GUIMenuSMS_UpdateStatus ( apMenu );

   }  /* end if */

  }  /* end if */

  apMenu -> Redraw ( apMenu );

 }  /* end if */

}  /* end _smb_handler */

static SMS_ListNode* _smb_active_node ( void ) {

 SMS_ListNode* lpNode;

 if (  !g_Config.m_pSMBList || !g_Config.m_pSMBList -> m_Size  ) return NULL;

 lpNode = g_Config.m_pSMBList -> m_pHead;

 while ( lpNode ) {

  SMBLoginInfo* lpInfo = ( SMBLoginInfo* )( unsigned int )lpNode -> m_Param;

  if (  !strcmp ( lpInfo -> m_ServerIP, g_Config.m_SMBIP )  ) return lpNode;

  lpNode = lpNode -> m_pNext;

 }  /* end while */

 return g_Config.m_pSMBList -> m_pHead;

}  /* end _smb_active_node */

static void _smb_reopen ( GUIMenu* apMenu ) {

 /* The current top state is the server list. It stashed the parent menu's
  * event handler (GUIMenuSMS_HandleEvent) in m_pState. Restore it before we
  * pop + rebuild so the fresh server list re-installs the SMB handler over a
  * clean parent (otherwise back-navigation would chain the SMB handler). */
 GUIMenuState* lpState = (  ( GUIMenuState* )( unsigned int )apMenu -> m_pState -> m_pTail -> m_Param  );

 int (  *lpParentEvent ) ( GUIObject*, u64  ) = lpState -> HandleEvent;

 GUI_MenuPopState ( apMenu );  /* drop the (now stale) server list */

 if ( lpParentEvent ) apMenu -> HandleEvent = lpParentEvent;

 _smb_menu ( apMenu );

}  /* end _smb_reopen */

static void _smb_add_handler ( GUIMenu* apMenu, int aDir ) {

 _smb_addedit_form ( apMenu, NULL );

}  /* end _smb_add_handler */

static void _smb_edit_handler ( GUIMenu* apMenu, int aDir ) {

 SMS_ListNode* lpNode = _smb_active_node ();

 if ( lpNode ) _smb_addedit_form ( apMenu, lpNode );

}  /* end _smb_edit_handler */

static void _smb_delete_handler ( GUIMenu* apMenu, int aDir ) {

 SMS_ListNode* lpNode = _smb_active_node ();

 if ( !lpNode ) return;

 g_Config.m_SMBIP[ 0 ] = '\x00';

 free (  ( void* )( unsigned int )lpNode -> m_Param  );
 SMS_ListRemove ( g_Config.m_pSMBList, lpNode );

 if ( !g_Config.m_pSMBList -> m_Size ) {
  g_IOPFlags              &= ~SMS_IOPF_SMBINFO;
  g_Config.m_NetworkFlags &= ~SMS_DF_SMB;
 }  /* end if */

 SMS_SaveSMBInfo ();

 _smb_reopen ( apMenu );

}  /* end _smb_delete_handler */

void _smb_menu ( GUIMenu* apMenu ) {

 int           i, lnItems, lnTotal, lFound;
 GUIMenuState* lpState = GUI_MenuPushState ( apMenu );
 SMBInfo*      lpInfo  = ( SMBInfo* )malloc (  sizeof ( SMBInfo )  );
 SMS_ListNode* lpNode  = g_Config.m_pSMBList ? g_Config.m_pSMBList -> m_pHead : NULL;

 lnItems = g_Config.m_pSMBList ? g_Config.m_pSMBList -> m_Size : 0;

 /* server rows + "Add server..." + ( "Edit..." + "Delete" when non-empty ) */
 lnTotal = lnItems + ( lnItems ? 3 : 1 );

 lpInfo -> m_Title.m_pStr = ( char* )calloc ( 1, i = STR_SMB_SERVER.m_Len - 2 );
 strncpy ( lpInfo -> m_Title.m_pStr, STR_SMB_SERVER.m_pStr, --i );
 lpInfo -> m_Title.m_Len  = i;

 lpInfo -> m_pItems   = ( GUIMenuItem* )calloc (  lnTotal, sizeof ( GUIMenuItem )  );
 lpInfo -> m_pStrings = ( SMString*    )calloc (  lnItems ? lnItems : 1, sizeof ( SMString )  );
 lpInfo -> m_CurIdx   = 0;
 lFound               = 0;

 for ( i = 0; i < lnItems; ++i, lpNode = lpNode -> m_pNext ) {

  lpInfo -> m_pItems[ i ].m_pOptionName = lpInfo -> m_pStrings + i;
  lpInfo -> m_pItems[ i ].Handler       = _smb_handler;

  lpInfo -> m_pStrings[ i ].m_pStr = _STR( lpNode );
  lpInfo -> m_pStrings[ i ].m_Len  = strlen (  _STR( lpNode )  );

  if (  !strcmp (
          g_Config.m_SMBIP, (  ( SMBLoginInfo* )( unsigned int )lpNode -> m_Param  ) -> m_ServerIP
         )
  ) {
   lpInfo -> m_CurIdx                  = i;
   lpInfo -> m_pItems[ i ].m_IconRight = GUICON_ON;
   lFound                              = 1;
  }  /* end if */

 }  /* end for */

 if ( lnItems && !lFound ) lpInfo -> m_pItems -> m_IconRight = GUICON_ON;

 lpInfo -> m_pItems[ i   ].m_pOptionName = &s_StrAddServer;
 lpInfo -> m_pItems[ i   ].m_IconRight   = GUICON_FOLDER;
 lpInfo -> m_pItems[ i++ ].Handler       = _smb_add_handler;

 if ( lnItems ) {

  lpInfo -> m_pItems[ i   ].m_pOptionName = &s_StrEditServer;
  lpInfo -> m_pItems[ i++ ].Handler       = _smb_edit_handler;

  lpInfo -> m_pItems[ i   ].m_pOptionName = &STR_DELETE;
  lpInfo -> m_pItems[ i++ ].Handler       = _smb_delete_handler;

 }  /* end if */

 lpState -> m_pItems           =
 lpState -> m_pFirst           =
 lpState -> m_pCurr            =  lpInfo -> m_pItems;
 lpState -> m_pLast            =  lpInfo -> m_pItems + lnTotal - 1;
 lpState -> m_pTitle           = &lpInfo -> m_Title;
 lpState -> m_pUserData        =  lpInfo;
 lpState -> UserDataDestructor =  _user_data_destructor;

 lpState -> HandleEvent = apMenu -> HandleEvent;
 apMenu  -> HandleEvent = GUIMenuSMB_HandleEvent;

 GUIMenuSMS_UpdateStatus ( apMenu );
 apMenu -> Redraw ( apMenu );

}  /* end _smb_menu */

