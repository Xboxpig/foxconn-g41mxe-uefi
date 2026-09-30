/* SPDX-License-Identifier: GPL-2.0-only */

#ifndef SOUTHBRIDGE_INTEL_I82801GX_CFR_H
#define SOUTHBRIDGE_INTEL_I82801GX_CFR_H

#include <drivers/option/cfr_frontend.h>
#include <southbridge/intel/common/pmutil.h>

#include "chip.h"

static const struct sm_object power_on_after_fail = SM_DECLARE_ENUM({
	.opt_name	= "power_on_after_fail",
	.ui_name	= "Restore After AC Power Loss",
	.ui_helptext	= "Select the system state after AC power is restored.",
	.default_value	= CONFIG_MAINBOARD_POWER_FAILURE_STATE,
	.values		= (const struct sm_enum_value[]) {
				{ "Power off",      MAINBOARD_POWER_OFF  },
				{ "Power on",       MAINBOARD_POWER_ON   },
				#if !CONFIG(BOARD_FOXCONN_G41MXE)
				{ "Previous state", MAINBOARD_POWER_KEEP },
				#endif
				SM_ENUM_VALUE_END },
});

static const struct sm_object sata_mode = SM_DECLARE_ENUM({
	.opt_name	= "sata_mode",
	.ui_name	= "SATA Controller Mode",
	.ui_helptext	= "Changing SATA mode can prevent an installed operating system "
			  "from booting until its matching storage driver is enabled.",
	.default_value	= CONFIG(BOARD_FOXCONN_G41MXE) ? SATA_MODE_IDE_PLAIN : SATA_MODE_AHCI,
	.values		= (const struct sm_enum_value[]) {
				#if !CONFIG(BOARD_FOXCONN_G41MXE)
				{ "AHCI",                SATA_MODE_AHCI                },
				#endif
				{ "IDE Legacy Combined", SATA_MODE_IDE_LEGACY_COMBINED },
				{ "IDE Native",          SATA_MODE_IDE_PLAIN           },
				SM_ENUM_VALUE_END },
});

static const struct sm_object nmi = SM_DECLARE_BOOL({
	.opt_name	= "nmi",
	.ui_name	= "Non-maskable Interrupts",
	.ui_helptext	= "Enable hardware non-maskable interrupt sources.",
	.default_value	= false,
});

#endif /* SOUTHBRIDGE_INTEL_I82801GX_CFR_H */
