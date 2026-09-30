#!/usr/bin/env python3
"""Target-only G41MXE EC snapshot: write selectors, never control registers."""
import json
import os
from pathlib import Path
import time


def pci_id(device):
    base = Path('/sys/bus/pci/devices') / device
    return (int((base / 'vendor').read_text(), 16),
            int((base / 'device').read_text(), 16))


if pci_id('0000:00:00.0') != (0x8086, 0x2e30) or \
        pci_id('0000:00:1f.0') != (0x8086, 0x27b8):
    raise SystemExit('Refusing: not the verified G41 / ICH7 target')
if Path('/sys/module/it87').exists():
    raise SystemExit('Refusing concurrent indexed EC access with it87 loaded')

# Base 0xa10 was verified from this board's IT8720F LDN4 resources.
# Only 0xa15 (index selector) is written; 0xa16 (register data) is read-only.
fd = os.open('/dev/port', os.O_RDWR)
old_index = os.pread(fd, 1, 0xa15)


def ec(index):
    os.pwrite(fd, bytes([index]), 0xa15)
    return os.pread(fd, 1, 0xa16)[0]


try:
    if ec(0x58) != 0x90 or not ec(0) & 1:
        raise SystemExit('Refusing: EC identity/monitor enable check failed')
    for sample in range(3):
        registers = [0, 0xa, 0xc, *range(0xd, 0x1b), *range(0x20, 0x2c),
                     0x50, 0x51, 0x55, 0x58]
        raw = {f'{r:02x}': ec(r) for r in registers}
        fans = []
        for fan in range(3):
            rpm = None
            for retry in range(3):
                high = ec(0x18 + fan)
                low = ec(0xd + fan)
                if high != ec(0x18 + fan):
                    continue
                count = high * 256 + low
                if raw['0c'] & (1 << fan) and count not in (0, 65535):
                    rpm = 1350000 // (count * 2)
                break
            fans.append(rpm)
        cores = {}
        for hwmon in Path('/sys/class/hwmon').glob('hwmon*'):
            if (hwmon / 'name').read_text().strip() != 'coretemp':
                continue
            for label in hwmon.glob('temp*_label'):
                value = label.with_name(label.name.replace('_label', '_input'))
                cores[label.read_text().strip()] = int(value.read_text())
        print(json.dumps({'sample': sample, 'time_ns': time.time_ns(),
                          'ec_raw': raw, 'fan_rpm': fans,
                          'coretemp_millidegrees': cores}), flush=True)
        if sample < 2:
            time.sleep(1)
finally:
    os.pwrite(fd, old_index, 0xa15)
    os.close(fd)
