"""Compile actual enable_tmpin with fake EC I/O; verify retained mode transitions."""
from pathlib import Path
import subprocess
import tempfile

directory = Path(__file__).resolve().parents[2] / 'build/coreboot/src/superio/ite/common'
source = (directory / 'env_ctrl.c').read_text()
start = source.index('static void enable_tmpin(')
end = source.index('\n}\n', start) + 3
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;
typedef int8_t s8;
typedef uint16_t u16;
struct device;
#define CONFIG(x) CONFIG_##x
#define CONFIG_SUPERIO_ITE_IT8720F 1
#define CONFIG_SUPERIO_ITE_IT8721F 0
#define CONFIG_SUPERIO_ITE_ENV_CTRL_TMPIN_SRC_SEL 0
#define CONFIG_SUPERIO_ITE_ENV_CTRL_EXT_ANY_TMPIN 0
#include "env_ctrl.h"
#define printk(...) ((void)0)
static u8 registers[256];
static unsigned writes;
static u8 pnp_read_hwm5_index(u16 base, u8 index) {
    assert(base == 0xa10); return registers[index];
}
static void pnp_write_hwm5_index(u16 base, u8 index, u8 value) {
    assert(base == 0xa10); registers[index] = value; ++writes;
}
static void set_tmpin_source(u16 base, u8 tmpin, u8 source) {
    (void)base; (void)tmpin; (void)source; assert(0);
}
static void enable_peci(u16 base) { (void)base; assert(0); }
'''
suffix = r'''
int main(void) {
    for (unsigned channel = 1; channel <= 3; ++channel) {
        unsigned diode = 1U << (channel - 1), resistor = 1U << (channel + 2);
        for (unsigned old = 0; old < 256; ++old) {
            for (unsigned mode = THERMAL_DIODE; mode <= THERMAL_RESISTOR; ++mode) {
                memset(registers, 0, sizeof(registers));
                registers[0x51] = old;
                struct ite_ec_thermal_config conf = {.mode = mode};
                enable_tmpin(0xa10, channel, &conf);
                unsigned expected = mode == THERMAL_DIODE ?
                    (old & ~resistor) | diode : (old & ~diode) | resistor;
                assert(registers[0x51] == expected);
            }
        }
    }
    registers[0x51] = 0x11;
    struct ite_ec_thermal_config conf = {.mode = THERMAL_DIODE};
    enable_tmpin(0xa10, 2, &conf);
    assert(registers[0x51] == 3);
    unsigned previous = writes;
    conf.mode = THERMAL_MODE_DISABLED;
    enable_tmpin(0xa10, 3, &conf);
    assert(writes == previous);
    puts("PASS: 1536 analog mode transitions; G41MXE 11 -> 03; disabled unchanged");
}
'''
with tempfile.TemporaryDirectory(prefix='g41-it8720-test-') as temp:
    fixture = Path(temp) / 'test.c'
    fixture.write_text(prefix + source[start:end] + suffix)
    binary = Path(temp) / 'test'
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-g', '-I', str(directory), str(fixture), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
