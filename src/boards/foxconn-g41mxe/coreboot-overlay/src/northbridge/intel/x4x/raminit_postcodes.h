/* SPDX-License-Identifier: GPL-2.0-or-later */

#ifndef NORTHBRIDGE_INTEL_X4X_RAMINIT_POSTCODES_H
#define NORTHBRIDGE_INTEL_X4X_RAMINIT_POSTCODES_H

#include <console/console.h>
#include <types.h>

/*
 * Gaps in coreboot's common POST-code allocation are used deliberately so
 * the last value observed on a port-80 card identifies the active operation.
 */
enum x4x_raminit_post_code {
	/* Per-DIMM codes add the DIMM index (0..3) to these base values. */
	X4X_POST_SPD_PROBE_BASE		= 0x50,
	X4X_POST_SPD_READ_BASE		= 0x54,
	X4X_POST_SPD_DECODE_BASE	= 0x58,
	X4X_POST_SPD_READY_BASE		= 0x5c,

	X4X_POST_DO_RAMINIT_ENTER	= 0xb0,
	X4X_POST_CLOCK_FREQUENCY	= 0xb1,
	X4X_POST_CLOCK_CROSSING		= 0xb2,
	X4X_POST_IO_CLOCK		= 0xb3,
	X4X_POST_DRAM_LAUNCH		= 0xb4,
	X4X_POST_DRAM_TIMINGS		= 0xb5,
	X4X_POST_DLL			= 0xb6,
	X4X_POST_RCOMP			= 0xb7,
	X4X_POST_ODT			= 0xb8,
	X4X_POST_RCOMP_UPDATE_WAIT	= 0xb9,
	X4X_POST_PRE_JEDEC		= 0xba,
	X4X_POST_JEDEC			= 0xbb,
	X4X_POST_DDR3_LEVELING_RESET	= 0xbc,
	X4X_POST_POST_JEDEC		= 0xbd,
	X4X_POST_DUMMY_READS		= 0xbe,
	X4X_POST_RECEIVE_ENABLE		= 0xbf,
	X4X_POST_WRITE_TRAINING		= 0xc0,
	X4X_POST_READ_TRAINING		= 0xc1,
	X4X_POST_DRADRB			= 0xc2,
	X4X_POST_MEMORY_MAP		= 0xc3,
	X4X_POST_ENHANCED_MODE		= 0xc4,
	X4X_POST_PERIODIC_RCOMP		= 0xc5,
	X4X_POST_POWER_SETTINGS		= 0xc6,
	X4X_POST_DO_RAMINIT_DONE	= 0xc7,

	X4X_POST_SDRAM_ENTER		= 0xd0,
	X4X_POST_MRC_CACHE_PROBED	= 0xd1,
	X4X_POST_RESET_CHECK		= 0xd2,
	X4X_POST_FSB_DETECT		= 0xd3,
	X4X_POST_DIMM_CONFIG		= 0xd4,
	X4X_POST_CALL_DO_RAMINIT	= 0xd5,
	X4X_POST_DO_RAMINIT_RETURNED	= 0xd6,
	X4X_POST_CBMEM_RECOVERY		= 0xd7,
	X4X_POST_MRC_CACHE_STASH	= 0xd8,
	X4X_POST_SDRAM_DONE		= 0xd9,
	X4X_POST_NO_USABLE_DIMM		= 0xde,
};

static inline void x4x_raminit_post(u8 value)
{
	if (CONFIG(X4X_RAMINIT_POSTCODES))
		post_code(value);
}

#endif
