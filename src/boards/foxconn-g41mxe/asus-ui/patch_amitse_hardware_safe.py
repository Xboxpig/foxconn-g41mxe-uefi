"""Remove remaining Z490 hardware access from the G41 display-validity AMITSE."""

import argparse
import hashlib
from pathlib import Path
import struct


SOURCE_HASH = "7df33b6d2572d9e925d79193ccb109cb823051a4b6e7afc4d7d5b7d92f65b4a8"

PM_TIMER_SITES = (0xB51, 0xB6B, 0xEB7C, 0xEB98)
SAFE_RETURN_SITES = {
    0x3D9D8: "48895c240848896c24104889742418",
    0xBA414: "4883ec28440fb6c9b8cdcccccc41f7",
    0x465D4: "40555357488bec4883ec608365e800",
}


def patch(source: bytes) -> bytes:
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError("Requires exact AMITSE display-validity v12 input")

    output = bytearray(source)
    for site in PM_TIMER_SITES:
        expected = bytes.fromhex("ba08180000")
        assert source[site : site + len(expected)] == expected
        output[site : site + len(expected)] = bytes.fromhex("ba08050000")

    # These entry points either operate unsupported Z490 hardware or are
    # installed as callbacks.  Return EFI_SUCCESS/zero before any prologue or
    # I/O instruction executes; the unreachable body remains byte-for-byte.
    for site, expected_hex in SAFE_RETURN_SITES.items():
        expected = bytes.fromhex(expected_hex)
        assert source[site : site + len(expected)] == expected
        output[site : site + 3] = bytes.fromhex("31c0c3")

    # Skip the donor 0x2e/0x2f Super I/O writes while retaining the function's
    # output initialization and mode-selection logic at 0xca477.
    site = 0xCA428
    target = 0xCA477
    expected = bytes.fromhex("4c8bca4c8bd141bb2e000000")
    assert source[site : site + len(expected)] == expected
    output[site : site + 5] = b"\xe9" + struct.pack("<i", target - site - 5)

    return bytes(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    candidate = patch(args.source.read_bytes())
    args.output.write_bytes(candidate)
    print("Hardware-safe AMITSE:", hashlib.sha256(candidate).hexdigest())
