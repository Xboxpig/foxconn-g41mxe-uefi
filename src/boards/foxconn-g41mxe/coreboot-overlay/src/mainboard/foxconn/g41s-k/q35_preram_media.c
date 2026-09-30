/* SPDX-License-Identifier: GPL-2.0-only */

#include <boot_device.h>

/*
 * QEMU's parallel flash enters command/status mode for the whole device.
 * G41 romstage executes XIP, so probing writable flash there would also
 * replace its instruction stream.  Pre-RAM users only need a region device
 * for validation; defer actual write and erase support to ramstage and SMM.
 */
const struct region_device *boot_device_rw(void)
{
	return boot_device_ro();
}
