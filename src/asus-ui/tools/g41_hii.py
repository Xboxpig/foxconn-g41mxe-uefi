"""Strict, dependency-free reader for the pinned ASUS PE HII resources."""
import struct


def u16(data, offset=0):
    return struct.unpack_from('<H', data, offset)[0]


def u32(data, offset=0):
    return struct.unpack_from('<I', data, offset)[0]


def packages(image):
    pe = u32(image, 0x3c)
    assert image[:2] == b'MZ' and image[pe:pe+4] == b'PE\0\0'
    section_table = pe + 24 + u16(image, pe + 20)
    resource_rva = u32(image, pe + 24 + 112 + 16)
    def offset(rva):
        for index in range(u16(image, pe + 6)):
            section = section_table + 40 * index
            start, size, raw = struct.unpack_from('<III', image, section + 12)
            if start <= rva < start + size:
                return raw + rva - start
        raise ValueError('Unbacked resource RVA')
    resource = offset(resource_rva)
    def entries(directory):
        count = u16(image, resource + directory + 12) + u16(image, resource + directory + 14)
        return [struct.unpack_from('<II', image, resource + directory + 16 + i*8) for i in range(count)]
    directories = entries(0)
    hii = []
    for name, target in directories:
        if name & 0x80000000:
            address = resource + (name & 0x7fffffff)
            length = u16(image, address)
            text = image[address+2:address+2+length*2].decode('utf-16-le')
            if text == 'HII':
                hii.append(target & 0x7fffffff)
    assert len(hii) == 1
    name = dict(entries(hii[0]))[1] & 0x7fffffff
    entry = resource + dict(entries(name))[0x409]
    start, size = offset(u32(image, entry)), u32(image, entry + 4)
    declared = u32(image, start + 16)
    assert declared <= size and start + size <= len(image)
    assert image[start+declared:start+size] == bytes(size-declared)
    size = declared
    result = []
    pos = start + 20
    while pos < start + size:
        header = u32(image, pos)
        length, kind = header & 0xffffff, header >> 24
        assert length >= 4 and pos + length <= start + size
        result.append((kind, image[pos:pos+length]))
        pos += length
    assert result[-1] == (0xdf, b'\x04\0\0\xdf')
    return start, size, entry, result


def string_blocks(package):
    pos, token = u32(package, 4), 1
    while pos < len(package):
        start, op = pos, package[pos]
        pos += 1
        if op == 0:
            assert pos == len(package)
            return
        if op == 0x14:
            text_start = pos
            while package[pos:pos+2] != b'\0\0':
                assert pos + 2 <= len(package)
                pos += 2
            text = package[text_start:pos].decode('utf-16-le')
            pos += 2
            yield token, start, pos, text
            token += 1
        elif op in (0x21, 0x22):
            width = 2 if op == 0x21 else 1
            token += int.from_bytes(package[pos:pos+width], 'little')
            pos += width
        elif op == 0x20:
            yield token, start, pos+2, None
            pos += 2
            token += 1
        else:
            raise ValueError(f'Unsupported string opcode {op:#x}')


def strings(package):
    result = {}
    for token, start, end, text in string_blocks(package):
        result[token] = text if text is not None else result[u16(package, start+1)]
    return result


def rewrite_strings(package, replacements):
    output, last = bytearray(), 0
    for token, start, end, text in string_blocks(package):
        if token in replacements:
            output.extend(package[last:start])
            output.extend(b'\x14' + (replacements[token] + '\0').encode('utf-16-le'))
            last = end
    output.extend(package[last:])
    struct.pack_into('<I', output, 0, len(output) | 4 << 24)
    return bytes(output)


class Node:
    def __init__(self, data):
        self.data = data
        self.children = []

    @property
    def op(self):
        return self.data[0]

    def encode(self):
        return self.data + b''.join(n.encode() for n in self.children) + (b'\x29\x02' if self.data[1] & 128 else b'')


def nodes(package):
    root, stack, pos = [], [], 4
    while pos < len(package):
        length = package[pos+1] & 127
        assert length >= 2 and pos + length <= len(package)
        node = Node(package[pos:pos+length])
        if node.op == 0x29:
            assert length == 2 and stack
            stack.pop()
        else:
            (stack[-1].children if stack else root).append(node)
            if node.data[1] & 128:
                stack.append(node)
        pos += length
    assert not stack
    return root


def walk(root):
    for node in root:
        yield node
        yield from walk(node.children)


def replace_packages(image, new_packages):
    start, size, entry, original = packages(image)
    body = b''.join(package for kind, package in new_packages)
    result = image[start:start+16] + struct.pack('<I', len(body) + 20) + body
    if len(result) > size:
        raise ValueError('Resource growth would overlap existing PE sections')
    output = bytearray(image)
    output[start:start+size] = result + bytes(size - len(result))
    struct.pack_into('<I', output, entry+4, len(result))
    # Preserve executable code, section RVAs, relocations and original donor.
    return bytes(output)
