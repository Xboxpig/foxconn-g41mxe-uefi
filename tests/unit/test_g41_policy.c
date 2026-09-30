#include <assert.h>
#include <stdio.h>
#include "../../src/boards/foxconn-g41mxe/coreboot-overlay/src/drivers/efi/asus_g41_policy.h"

int main(void)
{
	unsigned char fan[144] = {0}, sa[1282] = {0};
	unsigned int out = 99;
	assert(asus_g41_fan_policy(fan, sizeof(fan), 1, &out) && out == 3);
	fan[0] = 1;
	fan[8] = 0;
	assert(asus_g41_fan_policy(fan, sizeof(fan), 1, &out) && out == 1);
	fan[8] = 1;
	assert(asus_g41_fan_policy(fan, sizeof(fan), 1, &out) && out == 0);
	fan[0x18] = 3;
	fan[0x20] = 2;
	assert(asus_g41_fan_policy(fan, sizeof(fan), 0, &out) && out == 2);
	fan[8] = 3;
	out = 99;
	assert(!asus_g41_fan_policy(fan, sizeof(fan), 1, &out) && out == 99);
	fan[0] = 2;
	assert(!asus_g41_fan_policy(fan, sizeof(fan), 1, &out));
	assert(!asus_g41_fan_policy(fan, 143, 0, &out));
	assert(!asus_g41_fan_policy(fan, 144, 2, &out));
	assert(asus_g41_memory_policy(sa, sizeof(sa), &out) && out == 0);
	sa[0x18e] = 0x2b; sa[0x18f] = 4;
	assert(asus_g41_memory_policy(sa, sizeof(sa), &out) && out == 1066);
	sa[0x18e] = 0x35; sa[0x18f] = 5;
	assert(asus_g41_memory_policy(sa, sizeof(sa), &out) && out == 1333);
	sa[0x18e] = 0x40; sa[0x18f] = 6;
	out = 99;
	assert(!asus_g41_memory_policy(sa, sizeof(sa), &out) && out == 99);
	assert(!asus_g41_memory_policy(sa, 1281, &out));
	assert(!asus_g41_memory_policy(0, sizeof(sa), &out));
	puts("G41 donor policy conversions: PASS (14 cases)");
}
