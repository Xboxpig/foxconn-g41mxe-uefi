"""Pinned donor, IFR allowlist and PE injection boundary regression checks."""
from pathlib import Path
import struct
from g41_hii import nodes, packages, u16, walk
from patch_g41_platform_ui import (setup_patch, amitse_patch, question_id,
                                   QUESTIONS, NATIVE, NATIVE_STORE, PLATFORM_GUID)

root = Path(__file__).resolve().parents[2] / 'src/asus-ui/assets'
setup_source = (root / 'Setup-core2-zero-rpm.efi').read_bytes()
amitse_source = (root / 'AMITSE-hardware-safe.efi').read_bytes()
setup, _ = setup_patch(setup_source)
amitse = amitse_patch(amitse_source)
assert setup == (root / 'Setup-g41-v5.efi').read_bytes()
assert amitse == (root / 'AMITSE-g41-v5.efi').read_bytes()
ifr = nodes(next(p for kind, p in packages(setup)[3] if kind == 2))
all_nodes = list(walk(ifr))
forms = {u16(n.data, 2) for n in all_nodes if n.op == 1}
assert forms == {0x2710, 0x2713, 0x2714, 0x2715, 0x2716, 0x2718, 0x271a,
                 0x2858, 0x2740, 0x275a, 0x2793}
controls = {question_id(n): n for n in all_nodes if question_id(n) in QUESTIONS}
assert controls.keys() == QUESTIONS
for qid, choices in ((0x3a4, {0, 1067, 1333}), (0x285a, {0, 3}),
                     (0x28cf, {0, 3}), (0x2862, {0, 1, 2}), (0x28d7, {0, 1, 2})):
    node = controls[qid]
    assert not node.data[12] & 4
    assert {int.from_bytes(n.data[6:], 'little') for n in node.children if n.op == 9} == choices
assert any(n.op == 15 and u16(n.data, 6) == 0x105f and u16(n.data, 13) == 0x2858 for n in all_nodes)
assert all(n.op != 15 or len(n.data) == 15 for n in all_nodes)
native = {question_id(n): n for n in all_nodes if question_id(n) in {s['qid'] for s in NATIVE}}
assert len(native) == len(NATIVE)
for index, setting in enumerate(NATIVE):
    node = native[setting['qid']]
    assert u16(node.data, 8) == NATIVE_STORE and u16(node.data, 10) == index
    assert node.data[12] == 0x10 and node.data[13] == 0x10
    assert {n.data[6] for n in node.children} == {int(v) for v in setting['choices']}
    assert [n.data[6] for n in node.children if n.data[4] & 0x10] == [setting['default']]
    form = next(n for n in all_nodes if n.op == 1 and u16(n.data, 2) == setting['form'])
    assert node in form.children
store = next(n for n in all_nodes if n.op == 0x24 and u16(n.data, 18) == NATIVE_STORE)
assert store.data[2:18] == PLATFORM_GUID.bytes_le and u16(store.data, 20) == 16
for qid, fid in ((0x1be, 0x2740), (0x1c0, 0x275a), (0x1c1, 0x2793)):
    assert any(n.op == 15 and u16(n.data, 6) == qid and u16(n.data, 13) == fid for n in all_nodes)
pe = struct.unpack_from('<I', amitse, 60)[0]
sections = pe + 24 + 240
assert amitse[sections:sections + 280] == amitse_source[sections:sections + 280]
virtual, rva, raw_size, raw = struct.unpack_from('<4I', amitse, sections + 280 + 8)
assert rva == raw == 0x1dd080 and virtual <= raw_size
assert len(amitse) == raw + raw_size == struct.unpack_from('<I', amitse, pe + 24 + 56)[0]
assert struct.unpack_from('<I', amitse, pe + 24 + 64)[0] == 0
assert amitse[0x562df:0x562e3] == bytes.fromhex('4183ff02')
assert amitse[0xadeb4] == 0xe9
for source, patch in ((setup_source, setup_patch), (amitse_source, amitse_patch)):
    bad = bytearray(source)
    bad[-1] ^= 1
    try:
        patch(bytes(bad))
    except ValueError:
        pass
    else:
        raise AssertionError('Unpinned donor accepted')
print('PASS: exact donors, eleven G41 forms, native settings/store, compiled navigation IDs, PE bounds and hash guards')
