/* SPDX-License-Identifier: GPL-2.0-only */

#include <console/console.h>
#include <device/device.h>
#include <option.h>
#include <superio/ite/it8720f/it8720f.h>

static void set_pci_option(uint8_t slot, uint8_t function, const char *option,
			   bool fallback)
{
	struct device *dev = pcidev_on_root(slot, function);

	if (!dev)
		return;

	dev->enabled = get_uint_option(option, fallback);
	printk(BIOS_DEBUG, "G41MXE: %s %sabled by %s\n", dev_path(dev),
	       dev->enabled ? "en" : "dis", option);
}

static void set_pnp_option(uint8_t device, const char *option, bool fallback)
{
	struct device *dev = dev_find_slot_pnp(0x2e, device);

	if (!dev)
		return;

	dev->enabled = get_uint_option(option, fallback);
	printk(BIOS_DEBUG, "G41MXE: %s %sabled by %s\n", dev_path(dev),
	       dev->enabled ? "en" : "dis", option);
}

static void mainboard_init(void *chip_info)
{
	set_pci_option(0x1b, 0, "hd_audio", true);
	set_pci_option(0x1c, 1, "onboard_lan", true);
	set_pci_option(0x1f, 1, "pata_controller", true);

	set_pnp_option(IT8720F_FDC, "floppy_controller", true);
	set_pnp_option(IT8720F_SP1, "com1", true);
	set_pnp_option(IT8720F_SP2, "com2", true);
	set_pnp_option(IT8720F_PP, "parallel_port", true);
	set_pnp_option(IT8720F_CIR, "cir", true);
}

struct chip_operations mainboard_ops = {
	.init = mainboard_init,
};
