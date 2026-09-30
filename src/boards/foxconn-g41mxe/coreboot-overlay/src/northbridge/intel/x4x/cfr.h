/* SPDX-License-Identifier: GPL-2.0-only */

#ifndef NORTHBRIDGE_INTEL_X4X_CFR_H
#define NORTHBRIDGE_INTEL_X4X_CFR_H

#include <drivers/option/cfr_frontend.h>

static const struct sm_object gfx_uma_size = SM_DECLARE_ENUM({
	.opt_name	= "gfx_uma_size",
	.ui_name	= "Integrated Graphics Shared Memory",
	.ui_helptext	= "Memory reserved for the Intel GMA X4500 before the operating "
			  "system starts. The change takes effect after a reboot.",
	.default_value	= 6,
	.values		= (const struct sm_enum_value[]) {
				{ " 64 MiB", 6  },
				{ "128 MiB", 7  },
				{ "256 MiB", 8  },
				{ " 96 MiB", 9  },
				{ "160 MiB", 10 },
				{ "224 MiB", 11 },
				{ "352 MiB", 12 },
				SM_ENUM_VALUE_END },
});

static const struct sm_object max_mem_speed = SM_DECLARE_ENUM({
	.opt_name	= "max_mem_speed",
	.ui_name	= "Maximum Memory Data Rate",
	.ui_helptext	= "Limits memory speed to a value supported by the DIMMs and "
			  "chipset. This setting never overclocks memory. Changing it "
			  "forces memory retraining on the next boot.",
	.default_value	= 0,
	.values		= (const struct sm_enum_value[]) {
				{ "Automatic (SPD)", 0    },
				{ "DDR2-667",       667  },
				{ "DDR2/DDR3-800",  800  },
				{ "DDR3-1066",      1066 },
				{ "DDR3-1333",      1333 },
				SM_ENUM_VALUE_END },
});

#endif /* NORTHBRIDGE_INTEL_X4X_CFR_H */
