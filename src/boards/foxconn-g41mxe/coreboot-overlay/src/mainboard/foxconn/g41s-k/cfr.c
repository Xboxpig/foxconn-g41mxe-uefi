/* SPDX-License-Identifier: GPL-2.0-only */

#include <boot/coreboot_tables.h>
#include <drivers/option/cfr_frontend.h>
#include <northbridge/intel/x4x/cfr.h>
#include <southbridge/intel/i82801gx/cfr.h>
#include <superio/ite/it8720f/chip.h>

static const struct sm_object firmware_identity = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Foxconn G41MXE DIY Firmware",
	.ui_helptext	= "coreboot initializes the G41, ICH7 and IT8720F. EDK II provides "
			  "UEFI boot services and the LVGL graphical setup interface.",
});

static const struct sm_object firmware_storage = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Firmware storage: 16 MiB SPI / 512 KiB variable store",
	.ui_helptext	= "Boot-critical firmware remains in the upper 8 MiB for ICH7 address "
			  "compatibility. UEFI variables use the SMM-protected SMMSTORE area.",
});

static const struct sm_object platform_identity = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Platform: Intel G41 + ICH7 + ITE IT8720F",
	.ui_helptext	= "Native coreboot hardware initialization with a 64-bit EDK II UEFI "
			  "payload. Legacy CSM services are not required for UEFI boot.",
});

static const struct sm_object setup_navigation = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Boot entries are managed from the UEFI Boot Manager pages",
	.ui_helptext	= "This page controls coreboot hardware policy. Boot order, one-time boot "
			  "and EFI applications remain in the standard Tianocore menus.",
});

static const struct sm_object cpu_frequency_policy = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "FSB frequency and CPU multiplier: Hardware automatic",
	.ui_helptext	= "The processor supplies its supported FSB, voltage and multiplier. "
			  "Unsafe overclocking values are intentionally not exposed.",
});

static const struct sm_object eist = SM_DECLARE_BOOL({
	.opt_name	= "eist",
	.ui_name	= "Enhanced Intel SpeedStep",
	.ui_helptext	= "Allow a supported processor to change P-states for lower idle power. "
			  "The setting is applied and locked on the next boot.",
	.default_value	= true,
});

static const struct sm_object vmx = SM_DECLARE_BOOL({
	.opt_name	= "vmx",
	.ui_name	= "Intel Virtualization Technology (VT-x)",
	.ui_helptext	= "Enable hardware-assisted virtualization when supported by the CPU. "
			  "The change takes effect after a reboot.",
	.default_value	= CONFIG(ENABLE_VMX),
});

static const struct sm_object memory_training = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Memory timings: SPD training with cached fast boot",
	.ui_helptext	= "The firmware trains timings from each DIMM SPD. A data-rate change "
			  "invalidates the cache and performs a full retraining cycle.",
});

static const struct sm_object memory_fast_boot = SM_DECLARE_BOOL({
	.opt_name	= "memory_fast_boot",
	.ui_name	= "Memory Training Cache",
	.ui_helptext	= "Reuse verified training on normal boot. Disable to perform full "
			  "training after a cold reset. S3 resume always restores saved training.",
	.default_value	= true,
});

static const struct sm_object chipset_identity = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Northbridge graphics: Intel GMA X4500",
	.ui_helptext	= "Graphics is initialized natively by libgfxinit and exposed through "
			  "the UEFI Graphics Output Protocol.",
});

static const struct sm_object pata_controller = SM_DECLARE_BOOL({
	.opt_name	= "pata_controller",
	.ui_name	= "PATA / IDE Controller",
	.ui_helptext	= "Enable the ICH7 parallel ATA controller. Disable it when no PATA "
			  "device is installed to reduce device enumeration time.",
	.default_value	= true,
});

static const struct sm_object hd_audio = SM_DECLARE_BOOL({
	.opt_name	= "hd_audio",
	.ui_name	= "Intel HD Audio",
	.ui_helptext	= "Enable the onboard ICH7 HD Audio controller and codec.",
	.default_value	= true,
});

static const struct sm_object onboard_lan = SM_DECLARE_BOOL({
	.opt_name	= "onboard_lan",
	.ui_name	= "Onboard Realtek LAN",
	.ui_helptext	= "Enable the PCIe root port connected to the onboard RTL8168 network "
			  "controller.",
	.default_value	= true,
});

static const struct sm_object com1 = SM_DECLARE_BOOL({
	.opt_name	= "com1",
	.ui_name	= "Serial Port 1 (COM1, 3F8h)",
	.ui_helptext	= "Enable the first IT8720F serial port. Early firmware diagnostics may "
			  "still use this port before the setting is applied in ramstage.",
	.default_value	= true,
});

static const struct sm_object com2 = SM_DECLARE_BOOL({
	.opt_name	= "com2",
	.ui_name	= "Serial Port 2 (COM2, 2F8h)",
	.ui_helptext	= "Enable the second IT8720F serial port.",
	.default_value	= true,
});

static const struct sm_object parallel_port = SM_DECLARE_BOOL({
	.opt_name	= "parallel_port",
	.ui_name	= "Parallel Port (LPT1, 378h)",
	.ui_helptext	= "Enable the IT8720F legacy parallel port.",
	.default_value	= true,
});

static const struct sm_object floppy_controller = SM_DECLARE_BOOL({
	.opt_name	= "floppy_controller",
	.ui_name	= "Floppy Disk Controller",
	.ui_helptext	= "Enable the IT8720F floppy controller at 3F0h.",
	.default_value	= true,
});

static const struct sm_object cir = SM_DECLARE_BOOL({
	.opt_name	= "cir",
	.ui_name	= "Consumer Infrared Controller",
	.ui_helptext	= "Enable the IT8720F consumer infrared logical device.",
	.default_value	= true,
});

static const struct sm_object fan_profile = SM_DECLARE_ENUM({
	.opt_name	= "fan_profile",
	.ui_name	= "System and CPU Fan Profile",
	.ui_helptext	= "Select the IT8720F SmartGuardian curve for both connected fans. Full "
			  "Speed bypasses automatic PWM control.",
	.default_value	= ITE_FAN_PROFILE_BALANCED,
	.values		= (const struct sm_enum_value[]) {
				{ "Silent",      ITE_FAN_PROFILE_SILENT      },
				{ "Balanced",    ITE_FAN_PROFILE_BALANCED    },
				{ "Performance", ITE_FAN_PROFILE_PERFORMANCE },
				{ "Full Speed",  ITE_FAN_PROFILE_FULL_SPEED  },
				SM_ENUM_VALUE_END },
});

static const struct sm_object fan_monitor = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Monitoring controller: IT8720F SmartGuardian",
	.ui_helptext	= "TMPIN1 controls FAN1 and FAN2. Balanced uses 25 C off, 30 C start, "
			  "65 C full speed and 20 percent starting PWM.",
});

static const struct sm_object power_policy = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "CPU C-states and thermal protection: Automatic",
	.ui_helptext	= "Supported C2/C4/C5/C6 states, TM1/TM2, PROCHOT and PECI are configured "
			  "from processor capabilities for safe operation.",
});

static const struct sm_object security_model = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "Firmware variables protected by coreboot SMMSTORE",
	.ui_helptext	= "UEFI variable writes are mediated by the coreboot SMM handler. Secure "
			  "Boot key enrollment is not enabled in this build.",
});

static const struct sm_object post_success_beep = SM_DECLARE_BOOL({
	.opt_name	= "post_success_beep",
	.ui_name	= "Successful POST Beep",
	.ui_helptext	= "Emit one short tone immediately before starting the UEFI payload. "
			  "A passive speaker must be connected to the board header.",
	.default_value	= true,
});

static const struct sm_object diagnostic_policy = SM_DECLARE_COMMENT({
	.flags		= CFR_OPTFLAG_READONLY | CFR_OPTFLAG_VOLATILE,
	.ui_name	= "POST result: beep plus coreboot CBMEM log",
	.ui_helptext	= "A successful beep confirms coreboot reached payload handoff. Detailed "
			  "diagnostics remain available in the CBMEM console after boot.",
});

static struct sm_obj_form information = {
	.ui_name = "Main",
	.obj_list = (const struct sm_object *[]) {
		&firmware_identity,
		&platform_identity,
		&firmware_storage,
		&setup_navigation,
		NULL,
	},
};

static struct sm_obj_form cpu = {
	.ui_name = "CPU Configuration",
	.obj_list = (const struct sm_object *[]) {
		&cpu_frequency_policy,
		&eist,
		&vmx,
		NULL,
	},
};

static struct sm_obj_form memory = {
	.ui_name = "Memory Configuration",
	.obj_list = (const struct sm_object *[]) {
		&max_mem_speed,
		&memory_fast_boot,
		&memory_training,
		NULL,
	},
};

static struct sm_obj_form chipset = {
	.ui_name = "Chipset and Graphics",
	.obj_list = (const struct sm_object *[]) {
		&chipset_identity,
		&gfx_uma_size,
		NULL,
	},
};

static struct sm_obj_form storage = {
	.ui_name = "Storage Configuration",
	.obj_list = (const struct sm_object *[]) {
		&sata_mode,
		&pata_controller,
		NULL,
	},
};

static struct sm_obj_form onboard_devices = {
	.ui_name = "Onboard Devices",
	.obj_list = (const struct sm_object *[]) {
		&hd_audio,
		&onboard_lan,
		&com1,
		&com2,
		&parallel_port,
		&floppy_controller,
		&cir,
		NULL,
	},
};

static struct sm_obj_form hardware_monitor = {
	.ui_name = "Hardware Monitor and Fan Control",
	.obj_list = (const struct sm_object *[]) {
		&fan_profile,
		&fan_monitor,
		NULL,
	},
};

static struct sm_obj_form power = {
	.ui_name = "Power Management",
	.obj_list = (const struct sm_object *[]) {
		&power_on_after_fail,
		&power_policy,
		NULL,
	},
};

static struct sm_obj_form security = {
	.ui_name = "Security",
	.obj_list = (const struct sm_object *[]) {
		&security_model,
		NULL,
	},
};

static struct sm_obj_form diagnostics = {
	.ui_name = "Diagnostics",
	.obj_list = (const struct sm_object *[]) {
		&post_success_beep,
		&nmi,
		&diagnostic_policy,
		NULL,
	},
};

static struct sm_obj_form *sm_root[] = {
	&information,
	&cpu,
	&memory,
	&chipset,
	&storage,
	&onboard_devices,
	&hardware_monitor,
	&power,
	&security,
	&diagnostics,
	NULL,
};

void mb_cfr_setup_menu(struct lb_cfr *cfr_root)
{
	cfr_write_setup_menu(cfr_root, sm_root);
}
