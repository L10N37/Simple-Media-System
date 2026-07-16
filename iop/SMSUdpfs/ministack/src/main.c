#include <stdio.h>
#include <loadcore.h>
#include <irx.h>
#include <sysclib.h>

#include "main.h"
#include "smap.h"
#include "ministack_eth.h"
#include "ministack_ip.h"
/* udptty.h/.c are deliberately NOT built into SMS -- see the _start note below. */

IRX_ID(MODNAME, 0x1, 0x0);

extern struct irx_export_table _exp_mstack;

static uint32_t parse_ip(const char *sIP)
{
    int cp = 0;
    uint32_t part[4] = {0,0,0,0};

    while(*sIP != 0) {
        if(*sIP == '.') {
            cp++;
            if (cp >= 4)
                return 0; // Too many dots
        } else if(*sIP >= '0' && *sIP <= '9') {
            part[cp] = (part[cp] * 10) + (*sIP - '0');
            if (part[cp] > 255)
                return 0; // Too big number
        } else {
            return 0; // Invalid character
        }
        sIP++;
    }

    if (cp != 3)
        return 0; // Too little dots

    return IP_ADDR((uint8_t)part[0], (uint8_t)part[1], (uint8_t)part[2], (uint8_t)part[3]);
}

int _start(int argc, char *argv[])
{
    int i;

    /* Register RX callback with the smap driver, pre-reading 44 bytes (ETH+IP+UDP + app hdr) */
    smap_register_rx_callback(handle_rx_eth, 44);

    /* Parse command line IP address */
    for (i=1; i<argc; i++) {
        M_DEBUG("argv[%d] = %s\n", i, argv[i]);
        if (!strncmp(argv[i], "ip=", 3)) {
            uint32_t ip = parse_ip(&argv[i][3]);
            if (ip != 0)
                ms_ip_set_ip(ip);
        }
    }

/* Upstream calls udptty_init() here to redirect IOP printf over UDP. SMS must NOT:
 * it does close(0)/close(1), DelDrv/AddDrv the tty, then `while(1);` FOREVER unless the
 * reopened tty00: lands on exactly fd 0 and fd 1 ( udptty.c:75-89 ). SMS's IOP already
 * has its own tty/fd state by the time a network drive is started, so that is a coin
 * flip on a hard IOP hang -- a black screen with no diagnostic. It is debug-only
 * plumbing SMS never reads, so the call, udptty.o and the ioman imports it alone
 * needed are all dropped. Keep udptty.c in-tree ( unbuilt ) for upstream re-sync. */

    if (RegisterLibraryEntries(&_exp_mstack) != 0) {
        M_DEBUG("module already loaded\n");
        return MODULE_NO_RESIDENT_END;
    }

    return MODULE_RESIDENT_END;
}
