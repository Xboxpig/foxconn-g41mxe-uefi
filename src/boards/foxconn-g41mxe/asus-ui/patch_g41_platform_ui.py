"""Build a G41-only HII allowlist, retaining the genuine ASUS browser."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
from g41_hii import Node, nodes, packages, replace_packages, rewrite_strings, strings, u16, walk

SETUP_HASH = 'b2811e1a3db1bb2372574c54cf9400d3315ae2fed9d6dee7a4b6b8b8e8cc6bc7'
AMITSE_HASH = 'dc2fa602c5eacccb3c2923d0dd13625213ad173c6d36239b3daf1344f3a171c4'
VERSION = 'G41 v5'
NATIVE = json.loads((Path(__file__).parent / 'g41_native_settings.json').read_text())
CSM_NATIVE = json.loads((Path(__file__).parent / 'g41_csm_settings.json').read_text())
PLATFORM_GUID = uuid.UUID('fb3dca8b-eab5-4c93-9900-5247a7211886')
NATIVE_STORE = 0x7e01
# Only these donor settings have a reviewed coreboot consumer. Native options
# use the local ConfigAccess writer, never Z490 callbacks/registers.
QUESTIONS = {0x1064, 0x109e, 0x109f, 0x10a0,
             0x03a4, 0x285a, 0x2862, 0x28cf, 0x28d7}
SENSORS = ((0x14d8, 0x1fb3), (0x1fb8, 0x1fb9), (0x14da, 0x1fdf),
           (0x1fed, 0x1fee), (0x20ca, 0x20cb), (0x20cc, 0x20cd),
           (0x20ce, 0x20cf), (0x20d0, 0x20d1), (0x20d2, 0x20d3))


def text(prompt, value=2):
    return Node(b'\x03\x08' + struct.pack('<HHH', prompt, 2, value))


def ref(prompt, target, question=0x7e00):
    return Node(b'\x0f\x0f' + struct.pack('<HHHHHBH', prompt, 2, question, 0, 0xffff, 0, target))


def question_id(node):
    return u16(node.data, 6) if node.op in (5, 6, 7, 8, 12, 15, 28, 35) else None


def setup_patch(source, native_csm=False):
    native = NATIVE + CSM_NATIVE if native_csm else NATIVE
    if hashlib.sha256(source).hexdigest() != SETUP_HASH:
        raise ValueError('Requires the exact validated v4 Setup HII donor')
    _, _, _, original = packages(source)
    replacements = {0x0e: 'coreboot + EDK II', 0x10: '64-bit UEFI', 0x12: 'UEFI boot (no CSM)',
                    0x14: VERSION, 0x16: '2026-09-30', 0x1d71: 'Foxconn', 0x1d74: 'G41MXE rev 1.0',
                    0x1d6d: 'Memory', 0x1e: 'Platform', 0x1ee1: 'Firmware Tools',
                    0x1f: 'G41 / ICH7', 0x1f77: 'Changes apply after Save & Reset',
                    0x1f73: 'Fan tuning is not implemented on IT8720F',
                    0x06e3: 'Maximum DDR3 Data Rate', 0x06e4: 'SPD training cap; not an overclock. Applied on next boot.',
                    0x06e5: '1066 MT/s', 0x06e7: '1333 MT/s',
                    0x1fe0: 'CPU_FAN PWM Control', 0x1fef: 'SYS_FAN PWM Control',
                    0x1fed: 'SYS_FAN Speed', 0x1fe4: 'CPU_FAN Profile', 0x1ff4: 'SYS_FAN Profile',
                    0x20e2: 'Full Speed or PWM automatic control. Applied on next boot.',
                    0x20ed: 'IT8720F Standard / Silent / Turbo preset, applied on next boot.',
                    0x1f8c: 'Full Speed', 0x1f92: 'Balanced', 0x1f94: 'Performance',
                    0x20f9: 'CPU clock and voltage: Hardware automatic',
                    0x20fa: 'Memory timings: SPD training', 0x1f71: 'IT8720F Fan Configuration'}
    # Never expose the donor's sample readings while the real provider is
    # absent or still initializing. G41HiiSensors replaces these on success.
    replacements.update({value: 'N/A' for _, value in SENSORS})
    replacements.update({0x261: 'N/A', 0x266: 'N/A', 0x54a: 'N/A', 0x15dd: 'N/A'})
    replacements.update({0x2660: 'CPU Configuration', 0x2661: 'G41 Northbridge Configuration',
                         0x2662: 'ICH7 Southbridge Configuration',
                         0x2663: 'GMA X4500 / DDR3 (SPD training)',
                         0x2664: 'No XMP, DDR4 or VT-d on this G41 board.',
                         0x2665: 'Boot Architecture', 0x2666: 'UEFI only; CSM is not installed.',
                         0x2667: 'UEFI Boot Selection',
                         0x2668: 'Use Boot Menu (F8) or Shell bcfg. Shell and iPXE are manual tools.'})
    if native_csm:
        replacements.update({0x12: 'UEFI + Native CSM', 0x14: 'G41 v6 CSM',
                             0x2666: 'Native LegacyBios + Csm16. CSM policy applies after reset.',
                             0x2668: 'UEFI and Legacy disks share BootOrder. Shell and iPXE remain manual tools.'})
    native_tokens = {}
    option_token = 0x2680
    for index, setting in enumerate(native):
        prompt = 0x2600 + index * 2
        replacements[prompt] = setting['label']
        replacements[prompt + 1] = setting['help']
        options = []
        for value, label_text in setting['choices'].items():
            replacements[option_token] = label_text
            options.append((int(value), option_token))
            option_token += 1
        native_tokens[setting['qid']] = (index, prompt, options)
    output = []
    audit = []
    for kind, package in original:
        if kind == 4:
            output.append((kind, rewrite_strings(package, replacements)))
            continue
        if kind != 2:
            output.append((kind, package))
            continue
        root = nodes(package)
        assert len(root) == 1 and root[0].op == 0x0e
        formset = root[0]
        forms = {u16(n.data, 2): n for n in walk(root) if n.op == 1}
        original_questions = {question_id(n): n for n in walk(root) if question_id(n) is not None}
        questions = {question_id(n): n for n in walk(root) if question_id(n) in QUESTIONS}
        fan_link = next(n for n in walk(forms[0x2716].children)
                        if n.op == 15 and u16(n.data, 6) == 0x105f)
        assert QUESTIONS <= questions.keys(), QUESTIONS - questions.keys()
        native_questions = {}
        for setting in native:
            original_node = original_questions[setting['qid']]
            assert original_node.op == 5 and len(original_node.data) == 17
            index, prompt, options = native_tokens[setting['qid']]
            data = bytearray(original_node.data)
            struct.pack_into('<HH', data, 2, prompt, prompt + 1)
            struct.pack_into('<HH', data, 8, NATIVE_STORE, index)
            data[12] = 0x10  # Reset required; no donor callback.
            data[13:] = bytes((0x10, min(v for v, _ in options), max(v for v, _ in options), 0))
            node = Node(bytes(data))
            for value, token in options:
                node.children.append(Node(b'\x09\x07' + struct.pack('<HBBB', token,
                    0x30 if value == setting['default'] else 0, 0, value)))
            native_questions[setting['qid']] = node
            audit.append({'qid': hex(setting['qid']), 'store': hex(NATIVE_STORE),
                          'offset': hex(index), 'consumer': setting['name']})
        # Strip all platform-specific suppress expressions and callbacks. Their
        # dependencies are Z490-only; only reviewed plain NVRAM controls remain.
        for qid, node in questions.items():
            if node.op in (5, 7):
                data = bytearray(node.data)
                data[12] &= ~4  # EFI_IFR_FLAG_CALLBACK
                node.data = bytes(data)
            if node.op == 5:
                allowed = {0, 1, 3} if qid in (0x285a, 0x28cf) else ({0, 1, 2} if qid in (0x2862, 0x28d7) else ({0, 1067, 1333} if qid == 0x3a4 else None))
                if allowed is not None:
                    node.children = [n for n in node.children if n.op == 9 and int.from_bytes(n.data[6:], 'little') in allowed]
                if qid in (0x285a, 0x28cf):
                    # Default PWM (Auto remains a compatible older saved value).
                    node.children = [n for n in node.children if n.op != 9 or n.data[6] != 1]
                    for n in node.children:
                        data = bytearray(n.data)
                        data[4] = (data[4] & ~0x30) | (0x30 if data[6] == 3 else 0)
                        n.data = bytes(data)
            audit.append({'qid': hex(qid), 'store': hex(u16(node.data, 8)), 'offset': hex(u16(node.data, 10))})
        # Keep the original ASUS form IDs and presentation, not the Z490 setup.
        bodies = {
            0x2710: [ref(9, 0x2713, 2), ref(0x1d6d, 0x2714, 3), ref(0x1e, 0x2715, 4), ref(0x1eb4, 0x2716, 5), ref(0x20, 0x2718, 7), ref(0x4f, 0x271a, 9)],
            0x2713: [text(0x0d, 0x0e), text(0x13, 0x14), text(0x15, 0x16), text(0x1d6f, 0x1d71), text(0x1d72, 0x1d74), text(0x25f, 0x261), text(0x265, 0x266), text(0x15dc, 0x15dd), text(0x549, 0x54a)],
            0x2714: [text(0x20f9), text(0x20fa), questions[0x3a4]],
            0x2715: [text(0x1e, 0x1f), text(0x20f9), text(0x20fa)],
            0x2716: [text(prompt, value) for prompt, value in SENSORS] + [fan_link],
            0x2718: [questions[0x1064], text(0x2665, 0x2666), text(0x2667, 0x2668)],
            0x271a: [questions[q] for q in (0x109e, 0x109f, 0x10a0)],
            0x2858: [text(0x1f77)] + [questions[q] for q in (0x285a, 0x2862, 0x28cf, 0x28d7)],
        }
        for setting in native:
            bodies.setdefault(setting['form'], []).append(native_questions[setting['qid']])
        for qid, prompt in ((0x1be, 0x2660), (0x1c0, 0x2661), (0x1c1, 0x2662)):
            link = Node(original_questions[qid].data)
            data = bytearray(link.data)
            struct.pack_into('<HH', data, 2, prompt, 2)
            link.data = bytes(data)
            bodies[0x2715].append(link)
        bodies[0x2740].insert(0, text(0x20f9))
        bodies[0x275a].insert(0, text(0x2663))
        bodies[0x275a].append(text(0x2664))
        # AMITSE's compiled SPF dispatch needs the original question IDs for
        # links. Do not publish an inert cross-formset CFR link: its external
        # navigation path is not implemented by this donor browser.
        children = [n for n in formset.children if n.op in (0x24, 0x25, 0x26, 0x5c)]
        store_name = b'G41PlatformData\0'
        store = b'\x24' + bytes((22 + len(store_name),)) + PLATFORM_GUID.bytes_le
        store += struct.pack('<HH', NATIVE_STORE, 16) + store_name
        children.append(Node(store))
        for fid, body in bodies.items():
            form = forms[fid]
            title = {0x2740: 0x2660, 0x275a: 0x2661, 0x2793: 0x2662}.get(fid)
            if title is not None:
                data = bytearray(form.data)
                struct.pack_into('<H', data, 4, title)
                form.data = bytes(data)
            form.children = body
            children.append(form)
        formset.children = children
        new = b''.join(n.encode() for n in root)
        package = struct.pack('<I', len(new) + 4 | kind << 24) + new
        nodes(package)  # Check every scope/length before publishing.
        output.append((kind, package))
    return replace_packages(source, output), audit


def amitse_patch(source, native_csm=False):
    if hashlib.sha256(source).hexdigest() != AMITSE_HASH:
        raise ValueError('Requires exact validated v4 hardware-safe AMITSE')
    output = bytearray(source)
    version = b'v6' if native_csm else b'v5'
    for offset, old, new in ((0x15ebf8, b'PRIME Z490-A', b'G41MXE'),
                             (0x166800, b'ASUS PRIME Z490-A ACPI BIOS Revision 3401', b'Foxconn G41MXE DIY UEFI G41 ' + version)):
        assert source[offset:offset+len(old)+1] == old + b'\0'
        output[offset:offset+len(old)+1] = new + bytes(len(old) + 1 - len(new))
    # Donor assembles its four-digit revision from two ASCII fragments.
    assert source[0x15ebec:0x15ebf4] == b'01\0\x0034\0\0'
    output[0x15ebec:0x15ebf4] = version + b'\0\x00\0\0\0\0'
    # The EZ fan list is generated separately from the layout tree. This board
    # has CPU_FAN and SYS_FAN only; do not instantiate the five Z490 headers.
    assert source[0x562df:0x562e3] == bytes.fromhex('4183ff07')
    output[0x562e2] = 2
    _, _, _, original = packages(bytes(output))
    output = bytearray(replace_packages(bytes(output), [
        (kind, rewrite_strings(package, {
            0x140: 'SYS FAN', 0x15b: 'SYS FAN', 0x194: 'SYS FAN',
            0x1ba: 'SYS FAN',
        }) if kind == 4 else package) for kind, package in original
    ]))
    # State 2 is the donor's suppressed state: ADEB4 dispatches it through
    # the view's +180 setter, and 6A754 disables rendering/hit testing. Keep
    # every object allocated because other donor code dereferences FindWidget.
    # Check ancestry as well, so a hidden panel cannot leave active children.
    hidden = (0xb812, 0xb816, 0xb817, 0xb818, 0xb819, 0xb82e, 0xb83b, 0xb849, 0xb84a,
              0xb853, 0xb854, 0xb855, 0xb856, 0xb85a,
              0x780e, 0x780f, 0x7812, 0x7813, 0x7816, 0x7817, 0x7818, 0x7824)
    base = (len(output) + 15) & ~15
    code, labels, fixups = bytearray(), {}, []
    def emit(hexcode):
        code.extend(bytes.fromhex(hexcode))
    def label(name):
        labels[name] = base + len(code)
    def branch(opcode, target):
        emit(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))
    emit('4989c8')  # r8 = original node, RCX survives ancestry traversal
    label('ancestor')
    emit('418b502c')
    for widget in hidden:
        emit('81fa' + struct.pack('<I', widget).hex())
        branch('0f84', 'hidden')
    emit('4d8b4038 4d85c0')
    branch('0f85', 'ancestor')
    displaced = bytes.fromhex('40534883ec20')
    assert source[0xadeb4:0xadeba] == displaced
    code.extend(displaced)
    branch('e9', 0xadeba)
    label('hidden')
    # Rejoin before the donor's two virtual calls, not a tail call to the
    # setter: +1a0 propagates the new state into the underlying widget tree.
    code.extend(displaced)
    emit('488bd9 b102')
    branch('e9', 0xadeda)
    for offset, target in fixups:
        address = labels[target] if isinstance(target, str) else target
        struct.pack_into('<i', code, offset, address - (base + offset + 4))
    output[0xadeb4:0xadeba] = b'\xe9' + struct.pack('<i', base-0xadeb9) + b'\x90'
    output.extend(bytes(base-len(output)) + code)
    # Extend the already-present executable .g41na section, without moving any
    # existing RVA, resource, relocation, or the core-clock validity adapter.
    pe = struct.unpack_from('<I', output, 0x3c)[0]
    section = pe + 24 + 240 + 7*40
    assert output[section:section+8] == b'.g41na\0\0'
    size, rva, old_raw_size, raw = struct.unpack_from('<4I', output, section+8)
    assert rva == raw == 0x1dd080
    struct.pack_into('<I', output, section+8, len(output)-rva)
    raw_size = (len(output)-raw+31) & ~31
    output.extend(bytes(raw+raw_size-len(output)))
    struct.pack_into('<I', output, section+16, raw_size)
    struct.pack_into('<I', output, pe+24+56, (rva+raw_size+31) & ~31)
    struct.pack_into('<I', output, pe+24+4,
                     struct.unpack_from('<I', output, pe+24+4)[0] + raw_size - old_raw_size)
    struct.pack_into('<I', output, pe+24+64, 0)  # No stale PE checksum.
    return bytes(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--native-csm', action='store_true')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Generated UI artifacts; never an EDK source directory')
    parser.add_argument('--header-output', type=Path, required=True,
                        help='Explicit ConfigAccess header path in the composed build tree')
    args = parser.parse_args()
    setup, audit = setup_patch((args.directory / 'Setup-core2-zero-rpm.efi').read_bytes(), args.native_csm)
    amitse = amitse_patch((args.directory / 'AMITSE-hardware-safe.efi').read_bytes(), args.native_csm)
    version = 'v6-csm' if args.native_csm else 'v5'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, blob in ((f'Setup-g41-{version}.efi', setup), (f'AMITSE-g41-{version}.efi', amitse)):
        (args.output_dir / name).write_bytes(blob)
        print(name, hashlib.sha256(blob).hexdigest())
    (args.output_dir / f'g41-{version}-ui-allowlist.json').write_text(json.dumps(audit, indent=2) + '\n')
    # Same schema drives the local ConfigAccess writer and the HII controls.
    header = ['/* Generated from g41_native_settings.json; do not edit. */',
              '#define G41_PLATFORM_BUFFER_SIZE 16',
              '#define G41_PLATFORM_GUID {0xfb3dca8b,0xeab5,0x4c93,{0x99,0x00,0x52,0x47,0xa7,0x21,0x18,0x86}}',
              'STATIC G41_NATIVE_OPTION mNativeOptions[] = {']
    for setting in NATIVE:
        mask = sum(1 << int(v) for v in setting['choices'])
        header.append(f'  {{L"{setting["name"]}", {setting["default"]}, 0x{mask:04x}}},')
    header.append('#ifdef G41_NATIVE_CSM')
    for setting in CSM_NATIVE:
        mask = sum(1 << int(v) for v in setting['choices'])
        header.append(f'  {{L"{setting["name"]}", {setting["default"]}, 0x{mask:04x}}},')
    header.append('#endif')
    header.append('};\n')
    args.header_output.parent.mkdir(parents=True, exist_ok=True)
    args.header_output.write_text('\n'.join(header))
