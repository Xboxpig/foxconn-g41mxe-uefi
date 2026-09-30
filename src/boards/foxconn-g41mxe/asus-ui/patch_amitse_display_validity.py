"""Add CPU/board temperature and Vcore/DRAM display validity to the Q35 donor.

No shared getter or graph arithmetic is changed. Not a flashable firmware.
"""
import argparse
import hashlib
from pathlib import Path
import struct

SOURCE_HASH = 'c89d3f32ff1ba5a937bef7d23cf0adf588815b40e592373ec180bc87bb4b7c2a'
BASE = 0x1dd080


def patch(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Requires exact q35-sensor-validity AMITSE donor')
    output = bytearray(source)
    code = bytearray()
    labels = {}
    fixups = []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def label(name):
        labels[name] = BASE + len(code)

    def relative(opcode, target):
        emit(opcode)
        fixups.append((len(code), target))
        code.extend(bytes(4))

    label('get')
    emit('53 4883ec20 488bda')  # preserve RBX, aligned EFI shadow space, output pointer
    relative('488b05', 0x176180)  # HWM protocol pointer, RIP-relative
    emit('4885c0')
    relative('0f84', 'missing')
    for kind, token in ((4, 0x9fb3), (3, 0xa0cb), (16, 0x9fb9), (19, 0xa0d3),
                        (0, 0xf000), (1, 0xf001), (2, 0xf002), (18, 0xf003),
                        (21, 0xf004), (22, 0xf005), (25, 0x9fdf), (26, 0x9fee),
                        (27, 0x9ffc), (28, 0xa00a), (29, 0xa024), (30, 0xa030),
                        (31, 0x9fec)):
        emit('83f9' + bytes([kind]).hex())
        relative('0f85', f'next_{kind}')
        emit('b9' + struct.pack('<I', token).hex())
        relative('e9', 'read')
        label(f'next_{kind}')
    relative('e9', 'missing')
    label('read')
    emit('ff10')
    relative('e9', 'store')
    label('missing')
    emit('b8ff7f0000')
    label('store')
    emit('8903 c7430400000000 31c0 4883c420 5b c3')

    for name, displaced, comparison, resume in (
            ('temperature', '4c8b45b7 4c8bc8', '4981f8ff7f0000', 0x3be29),
            ('voltage', '4c8b4db7 4c8bd0', '4981f9ff7f0000', 0x3bf16),
            ('board', '4c8b45b7 4c8bc8', '4981f8ff7f0000', 0x3c782),
            ('dram', '4c8b4db7 4c8bd0', '4981f9ff7f0000', 0x3c677),
            ('bclk', '4c8b4db7 4c8bd0', '4981f9ff7f0000', 0x3c062)):
        label(name)
        emit(displaced)
        emit(comparison)
        relative('0f84', 'na')
        relative('e9', resume)

    # This formatter saves RSI at entry. Use its otherwise-unused frequency
    # branch local to remember enum18 across allocator/provider calls.
    label('frequency_get')
    emit('31f6 83f912 400f94c6')
    relative('e9', 'get')

    for name, pattern, resume in (('frequency', 0x15eb98, 0x3c0c0),
                                   ('ratio', 0x15ebc0, 0x3c027),
                                   ('capacity', 0x15ebe0, 0x3c027)):
        label(name)
        relative('488d15', pattern)  # displaced format string address
        if name == 'frequency':
            emit('85f6')
            relative('0f84', 'frequency_unit_ready')
            relative('488d15', 'memory_rate_pattern')
            label('frequency_unit_ready')
        emit('4c8b45b7 4981f8ff7f0000')
        relative('0f84', 'na')
        relative('e9', resume)

    label('fan_output')
    emit('488b7db7 488bc7 4881ffff7f0000')
    relative('0f85', 'fan_store')
    emit('31c0')  # Preserve legacy numeric missing=0, never export 32767 RPM.
    label('fan_store')
    emit('498906')
    relative('e9', 0x3c99e)
    label('fan_validity')
    emit('4881ffff7f0000')
    relative('0f84', 0x3ca49)  # Original colored N/A path, RCX still allocation.
    relative('e9', 0x3c9c4)  # Includes valid zero and original low-speed styling.

    label('memory_type')
    emit('b916000000 488d5507')
    relative('e8', 'get')
    emit('4c393b')
    relative('0f84', 0x3c732)
    relative('e9', 0x3c72a)

    label('memory_summary')
    emit('4c8b4d7f 4c8b45b7')
    emit('4981f9ff7f0000')
    relative('0f84', 'na')
    emit('4981f8ff7f0000')
    relative('0f84', 'na')
    emit('48837d0703')
    relative('0f84', 'memory_ddr3')
    emit('48837d0702')
    relative('0f85', 'na')
    relative('488d15', 'ddr2_pattern')
    relative('e9', 0x3c74b)
    label('memory_ddr3')
    relative('488d15', 'ddr3_pattern')
    relative('e9', 0x3c74b)

    # SP and cooler points are donor AI-OC estimates, not EC sensors. Their
    # callbacks require ASUS training data absent on G41. Do not run them.
    label('unsupported_prediction')
    emit('4c393b')
    relative('0f84', 'prediction_allocate')
    emit('488bcb')
    relative('e8', 0x11c0)
    label('prediction_allocate')
    emit('b9a2000000')
    relative('e8', 0x12b8)
    relative('e9', 'na')

    for name in ('nonavx', 'avx', 'cache'):
        label(f'prediction_{name}')
        relative('488d35', f'prediction_{name}_pattern')
        relative('e9', 'prediction_label')
    label('prediction_label')
    emit('4c393b')
    relative('0f84', 'prediction_label_allocate')
    emit('488bcb')
    relative('e8', 0x11c0)
    label('prediction_label_allocate')
    emit('b9a2000000')
    relative('e8', 0x12b8)
    emit('488903 488bc8 488bd6')
    relative('e9', 0x3cac7)

    label('na')
    emit('488903 488bc8')  # retain original allocation ownership
    relative('488d15', 0x15eab8)  # original UTF-16 N/A literal
    relative('e9', 0x3cac7)  # original printf and original function epilogue
    if len(code) & 1:
        code.append(0xcc)  # Keep all UTF-16 data naturally aligned.
    label('memory_rate_pattern')
    code.extend(('%d MT/s' + '\0').encode('utf-16le'))
    for generation in (2, 3):
        label(f'ddr{generation}_pattern')
        code.extend((f'%d MB (DDR{generation} %d MT/s)' + '\0').encode('utf-16le'))
    for name, title in (('nonavx', 'NonAVX'), ('avx', 'AVX'), ('cache', 'Cache')):
        label(f'prediction_{name}_pattern')
        code.extend((title + ' V req\nfor N/A\0').encode('utf-16le'))
    for offset, target in fixups:
        address = labels[target] if isinstance(target, str) else target
        struct.pack_into('<i', code, offset, address - (BASE + offset + 4))

    sites = (
        (0x3be06, 'e89de1ffff', 'get', 0xe8),
        (0x3bef3, 'e8b0e0ffff', 'get', 0xe8),
        (0x3be22, '4c8b45b74c8bc8', 'temperature', 0xe9),
        (0x3bf0f, '4c8b4db74c8bd0', 'voltage', 0xe9),
        (0x3c75f, 'e844d8ffff', 'get', 0xe8),
        (0x3c77b, '4c8b45b74c8bc8', 'board', 0xe9),
        (0x3c654, 'e84fd9ffff', 'get', 0xe8),
        (0x3c670, '4c8b4db74c8bd0', 'dram', 0xe9),
        (0x3c09d, 'e806dfffff', 'frequency_get', 0xe8),
        (0x3c0b9, '488d15d82a1200', 'frequency', 0xe9),
        (0x3c03f, 'e864dfffff', 'get', 0xe8),
        (0x3c05b, '4c8b4db74c8bd0', 'bclk', 0xe9),
        (0x3c004, 'e89fdfffff', 'get', 0xe8),
        (0x3c020, '488d15992b1200', 'ratio', 0xe9),
        (0x3c5ef, 'e8b4d9ffff', 'get', 0xe8),
        (0x3c60b, '488d15ce251200', 'capacity', 0xe9),
        (0x3c712, 'e891d8ffff', 'get', 0xe8),
        (0x3c720, 'e883d8ffff', 'get', 0xe8),
        (0x3c725, '4c393b7408', 'memory_type', 0xe9),
        (0x3c73c, '4c8b4d7f488d15f9241200', 'memory_summary', 0xe9),
        (0x3bdb1, '4c393b7408', 'unsupported_prediction', 0xe9),
        (0x3c19d, '4c393b7408', 'unsupported_prediction', 0xe9),
        (0x3c259, '4c393b7408', 'prediction_nonavx', 0xe9),
        (0x3c221, '4c393b7408', 'prediction_avx', 0xe9),
        (0x3c3df, '4c393b7408', 'prediction_cache', 0xe9),
        (0x3c992, 'e811d6ffff', 'get', 0xe8),
        (0x3c997, '488b7db749893e', 'fan_output', 0xe9),
        (0x3c9bb, '4885ff0f8485000000', 'fan_validity', 0xe9),
    )
    for address, expected, target, opcode in sites:
        expected = bytes.fromhex(expected)
        assert source[address:address + len(expected)] == expected
        replacement = bytes([opcode]) + struct.pack('<i', labels[target] - address - 5)
        output[address:address + len(expected)] = replacement + b'\x90' * (len(expected) - 5)

    # This donor has no room for an eighth section header. Move its PE header
    # 40 bytes earlier into verified zero DOS-stub padding, retaining all section
    # RVAs/raw offsets and SizeOfHeaders. No donor code/data is shifted.
    old_pe, new_pe = 0xd8, 0xb0
    assert struct.unpack_from('<I', source, 0x3c)[0] == old_pe
    assert source[new_pe:old_pe] == bytes(40)
    assert source[old_pe:old_pe + 4] == b'PE\0\0'
    assert struct.unpack_from('<H', source, old_pe + 6)[0] == 7
    assert len(source) == BASE
    output[new_pe:0x2d8] = source[old_pe:0x300]
    struct.pack_into('<I', output, 0x3c, new_pe)
    struct.pack_into('<H', output, new_pe + 6, 8)
    optional = new_pe + 24
    assert struct.unpack_from('<II', output, optional + 32) == (32, 32)
    assert struct.unpack_from('<II', output, optional + 56) == (BASE, 0x300)
    size = (len(code) + 31) & ~31
    section_header = new_pe + 24 + 240 + 7 * 40
    assert section_header == 0x2d0
    output[section_header:section_header + 40] = struct.pack('<8sIIIIIIHHI', b'.g41na\0\0',
        len(code), BASE, size, BASE, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<I', output, optional + 56, BASE + size)
    old_code_size = struct.unpack_from('<I', output, optional + 4)[0]
    struct.pack_into('<I', output, optional + 4, old_code_size + size)
    struct.pack_into('<I', output, optional + 64, 0)  # no stale PE checksum
    output.extend(code + b'\xcc' * (size - len(code)))
    return bytes(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    candidate = patch(args.source.read_bytes())
    with args.output.open('xb') as stream:
        stream.write(candidate)
    print('EXPERIMENTAL display-only AMITSE:', hashlib.sha256(candidate).hexdigest())
