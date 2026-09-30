#!/usr/bin/env python3
"""Read only the verified G41 memory-controller status registers."""
import json
import mmap
import os
from pathlib import Path


def read_exact(fd, length, offset):
    value = os.pread(fd, length, offset)
    if len(value) != length:
        raise RuntimeError('Short hardware read')
    return int.from_bytes(value, 'little')


def main():
    root = Path('/sys/bus/pci/devices')
    for device, expected in [('0000:00:00.0', 0x2e30), ('0000:00:1f.0', 0x27b8)]:
        node = root / device
        if int((node / 'vendor').read_text(), 16) != 0x8086 or int((node / 'device').read_text(), 16) != expected:
            raise SystemExit('Refusing: not G41 / ICH7')
    fd = os.open(root / '0000:00:00.0/config', os.O_RDONLY)
    try:
        bar = read_exact(fd, 8, 0x48)
    finally:
        os.close(fd)
    # This address is independently confirmed by this board's PCI snapshot.
    if bar != 0xfed14001:
        raise SystemExit(f'Refusing unverified MCHBAR: {bar:#x}')
    fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
    try:
        with mmap.mmap(fd, 0x1000, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ,
                       offset=bar & ~0x3fff) as region:
            registers = {f'{offset:03x}': int.from_bytes(region[offset:offset + size], 'little')
                         for offset, size in [(0xc00, 4), (0x1a8, 1), (0x111, 1),
                                              (0x206, 2), (0x606, 2)]}
    finally:
        os.close(fd)
    code = (registers['c00'] >> 4) & 7
    rates = [400, 533, 667, 800, 1067, 1333]
    print(json.dumps({'mchbar': hex(bar), 'raw': registers,
                      'ddr_generation': 3 if registers['1a8'] & 4 else 2,
                      'selected_data_rate_mt_s': rates[code] if code < len(rates) else None,
                      'note': 'Configured clock encoding, not an independent frequency measurement; capacity not decoded.'}))


if __name__ == '__main__':
    main()
