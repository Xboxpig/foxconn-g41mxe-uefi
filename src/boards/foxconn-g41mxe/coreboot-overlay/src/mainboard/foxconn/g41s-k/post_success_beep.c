/* SPDX-License-Identifier: GPL-2.0-only */

#include <arch/io.h>
#include <bootstate.h>
#include <delay.h>
#include <option.h>

#define PIT_COUNTER_2_PORT	0x42
#define PIT_COMMAND_PORT	0x43
#define PC_SPEAKER_PORT		0x61

#define PIT_INPUT_HZ		1193180
#define POST_SUCCESS_TONE_HZ	1000
#define POST_SUCCESS_TONE_MS	180

static void post_success_beep(void *unused)
{
	if (!get_uint_option("post_success_beep", 1))
		return;

	const u16 divisor = PIT_INPUT_HZ / POST_SUCCESS_TONE_HZ;
	const u8 speaker_state = inb(PC_SPEAKER_PORT);

	outb(0xb6, PIT_COMMAND_PORT);
	outb(divisor & 0xff, PIT_COUNTER_2_PORT);
	outb(divisor >> 8, PIT_COUNTER_2_PORT);
	outb(speaker_state | 0x03, PC_SPEAKER_PORT);
	mdelay(POST_SUCCESS_TONE_MS);
	outb(speaker_state, PC_SPEAKER_PORT);
}

BOOT_STATE_INIT_ENTRY(BS_PAYLOAD_BOOT, BS_ON_ENTRY, post_success_beep, NULL);
