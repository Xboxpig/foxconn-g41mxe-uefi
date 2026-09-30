"""Native CSM controls use the reviewed local store, not Z490 callbacks."""
from pathlib import Path
from g41_hii import nodes, packages, walk, u16
from patch_g41_platform_ui import setup_patch, amitse_patch, NATIVE, CSM_NATIVE, NATIVE_STORE, question_id

root = Path(__file__).resolve().parents[2] / 'src/asus-ui/assets'
setup, audit = setup_patch((root / 'Setup-core2-zero-rpm.efi').read_bytes(), True)
assert setup == (root / 'Setup-g41-v6-csm.efi').read_bytes()
assert amitse_patch((root / 'AMITSE-hardware-safe.efi').read_bytes(), True) == (root / 'AMITSE-g41-v6-csm.efi').read_bytes()
ifr = nodes(next(p for kind, p in packages(setup)[3] if kind == 2))
boot = next(n for n in walk(ifr) if n.op == 1 and u16(n.data, 2) == 0x2718)
for index, setting in enumerate(CSM_NATIVE, len(NATIVE)):
    node = next(n for n in boot.children if question_id(n) == setting['qid'])
    assert u16(node.data, 8) == NATIVE_STORE
    assert u16(node.data, 10) == index
    assert node.data[12] == 0x10 and not node.data[12] & 4
    assert {n.data[6] for n in node.children} == {int(v) for v in setting['choices']}
    assert [n.data[6] for n in node.children if n.data[4] & 0x30] == [setting['default']]
assert len(audit) == len(NATIVE) + len(CSM_NATIVE) + 9
print('PASS: v6 pinned images; native Launch CSM/Boot Device Control; safe defaults and reset-required controls')
