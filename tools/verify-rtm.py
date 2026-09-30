"""Verify the G41 candidate against its preserved coreboot baseline and built FD."""
import hashlib
import lzma
from pathlib import Path
import struct
import uuid
from elftools.elf.elffile import ELFFile

root = Path(__file__).resolve().parents[1]
build = root / 'releases/g41mxe-rtm1/support'
candidate = root / 'releases/g41mxe-rtm1/g41mxe-rtm1-16m.rom'
baseline = build / 'coreboot-v5-base.rom'
rom, old = candidate.read_bytes(), baseline.read_bytes()
assert len(rom) == len(old) == 16 * 1024 * 1024
assert hashlib.sha256(old).hexdigest() == '545130a5a9f2d002afae0d724b30f49a1cdc34dcfdb59962506b2df89003b992'
assert rom[:0x891000] == old[:0x891000], 'MRC/SMMSTORE/FMAP changed'

def cbfs(blob):
    files = {}
    position = 0x891000
    while position < len(blob):
        position = blob.find(b'LARCHIVE', position)
        if position < 0:
            break
        size, kind, attributes, offset = struct.unpack_from('>4I', blob, position + 8)
        assert offset >= 24 and position + offset + size <= len(blob)
        name = blob[position + 24:position + offset].split(b'\0', 1)[0].decode()
        if name:
            assert name not in files
            files[name] = blob[position + offset:position + offset + size]
        position = (position + offset + size + 63) & ~63
    return files

files, original = cbfs(rom), cbfs(old)
assert files.keys() == original.keys()
for name in files:
    if name != 'fallback/payload':
        assert files[name] == original[name], name
payload = files['fallback/payload']
kind, compression, offset, load, size, memory_size = struct.unpack_from('>IIIQII', payload)
assert kind == 0x434f4445 and compression == 1 and load == 0x800000
fd = (build / 'UEFIPAYLOAD.fd').read_bytes()
assert hashlib.sha256(rom).hexdigest() == '24567d0a88a38d6dc592263e169e177d9fdd39bda39b92a79e5fd25060e8aa83'
assert lzma.decompress(payload[offset:offset + size]) == fd
assert memory_size == len(fd)

def fv_files(blob):
    assert blob[40:44] == b'_FVH'
    header_size = struct.unpack_from('<H', blob, 48)[0]
    assert sum(struct.unpack('<' + 'H' * (header_size // 2), blob[:header_size])) & 0xffff == 0
    position = (header_size + 7) & ~7
    result = {}
    while position + 24 <= len(blob) and blob[position:position + 24] != b'\xff' * 24:
        header = blob[position:position + 24]
        size = int.from_bytes(header[20:23], 'little')
        assert 24 <= size < 0xffffff and position + size <= len(blob)
        if header[18] != 0xf0:
            result[str(uuid.UUID(bytes_le=header[:16]))] = blob[position + 24:position + size]
        position = (position + size + 7) & ~7
    return result

dxe = (build / 'DXEFV.Fv').read_bytes()
assert dxe in fd, 'DXE FV not embedded in final FD'
modules = fv_files(dxe)
for guid in ('fbdd6b47-f280-47f8-b04c-e54f9f2c9e80', '79ca4208-bba1-4a9a-8456-e1e66a81484e',
             'f122a15c-c10b-4d54-8f48-60f4f06dd1ad', '6962b46d-1b83-4d86-af05-b4526d0a2cbf'):
    assert guid in modules, guid
assert '6e2f4063-d7a4-4b2d-a6c6-995d8ab18372' not in modules, 'Diagnostic app in hardware ROM'
for guid, path in (
    ('1547b4f3-3e8a-4fef-81c8-328ed647ab1a', build / 'Csm16.bin'),
    ('8d1ff5c2-2bc2-4c90-8f7f-ec395df3a649', root / 'src/boards/foxconn-g41mxe/edk2-overlay/UefiPayloadPkg/G41CsmSupportDxe/G41Vbios.rom')):
    raw = modules[guid]
    assert raw[3] == 0x19 and raw[4:] == path.read_bytes()
with (build / 'DxeCore.debug').open('rb') as stream:
    elf = ELFFile(stream)
    symbol = elf.get_section_by_name('.symtab').get_symbol_by_name('_gPcd_BinaryPatch_PcdDebugPropertyMask')[0]
    section = elf.get_section(symbol['st_shndx'])
    assert section.data()[symbol['st_value'] - section['sh_addr']] == 2
print('PASS: 16 MiB; baseline boot stages and MRC/SMMSTORE unchanged; exact decompressed FD; native CSM drivers; authentic P10 VBIOS; no diagnostic app; DxeCore mask=02')
print('ROM SHA256', hashlib.sha256(rom).hexdigest())
print('FD SHA256', hashlib.sha256(fd).hexdigest())
