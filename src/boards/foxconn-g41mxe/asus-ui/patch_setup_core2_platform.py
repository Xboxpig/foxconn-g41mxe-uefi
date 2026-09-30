"""X5450-only experiment: preserve donor unknown-platform result without Z490 MMIO."""
import argparse
import hashlib
from pathlib import Path


def patch(data):
    if hashlib.sha256(data).hexdigest() != 'a5f7caf7ca32d28fed3ddb505315b4a5b8c0e1f3ee83c8a385a135025fe4ab99':
        raise ValueError('Unexpected Setup donor; requires q35-sensor-validity')
    assert data[0x23d24:0x23d2c] == bytes.fromhex('4c8bdc534883ec40')
    # The original initializes BL=4. CPUID 10676, masked to 10670, matches
    # none of its modern CPU families and returns AL=4 regardless of host DID.
    # This does not enable a donor feature or claim G41 is a Z490 platform.
    result = bytearray(data)
    result[0x23d24:0x23d2a] = bytes.fromhex('b804000000c3')
    # Type 2 is the donor fan/RPM branch. Explicit unavailable (7fff) has
    # already branched out at 23089; a real zero must continue as 0 RPM.
    assert data[0x232d5:0x232de] == bytes.fromhex('4885ff0f8435010000')
    result[0x232d8:0x232de] = b'\x90' * 6
    return bytes(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = patch(args.source.read_bytes())
    with args.output.open('xb') as stream:
        stream.write(result)
    print('EXPERIMENTAL Core 2 Setup:', hashlib.sha256(result).hexdigest())
