/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef ASUS_G41_POLICY_H
#define ASUS_G41_POLICY_H

/* PRIME Z490-A 3401 IFR: AsusQFanSetupData, 144 bytes. Never accept other layouts. */
static inline int asus_g41_fan_policy(const unsigned char *data, unsigned int size,
				    unsigned int cpu, unsigned int *profile)
{
	unsigned int offset = cpu ? 0 : 0x18;
	if (!data || !profile || size != 144 || cpu > 1)
		return 0;
	if (data[offset] == 0) {
		*profile = 3; /* Q-Fan disabled means full speed, never fan stop. */
		return 1;
	}
	if (data[offset] != 1 && data[offset] != 3)
		return 0; /* DC mode is not validated on this PWM board. */
	switch (data[offset + 8]) {
	case 0: *profile = 1; return 1; /* Standard -> Balanced */
	case 1: *profile = 0; return 1; /* Silent */
	case 2: *profile = 2; return 1; /* Turbo -> Performance */
	default: return 0; /* Manual curves require a separate, validated conversion. */
	}
}

/* SaSetup offset 0x18e is a UINT16 MHz limit, not the Ai Tweaker DDR4 enum. */
static inline int asus_g41_memory_policy(const unsigned char *data, unsigned int size,
				       unsigned int *mhz)
{
	unsigned int value;
	if (!data || !mhz || size != 1282)
		return 0;
	value = data[0x18e] | (data[0x18f] << 8);
	switch (value) {
	case 0: *mhz = 0; return 1;
	case 1067: *mhz = 1066; return 1; /* Same JEDEC rate, different rounding. */
	case 1333: *mhz = 1333; return 1;
	default: return 0; /* Do not silently map DDR4-only speeds to G41. */
	}
}
#endif
