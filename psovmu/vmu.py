"""VMU filesystem parsing: directory listing, FAT chain traversal, and splicing an
edited file's bytes back into the full 256-block VMU image on disk."""
import struct

BLOCK = 512
ROOT_BLOCK = 255


def _bcd(b):
    return (b >> 4) * 10 + (b & 0xF)


def _parse_timestamp(ts):
    year = _bcd(ts[0]) * 100 + _bcd(ts[1])
    month, day, hour, minute, second = (
        _bcd(ts[2]), _bcd(ts[3]), _bcd(ts[4]), _bcd(ts[5]), _bcd(ts[6])
    )
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


class VMUFileEntry:
    def __init__(self, file_type, name, start_block, size_blocks, saved):
        self.file_type = file_type
        self.name = name
        self.start_block = start_block
        self.size_blocks = size_blocks
        self.saved = saved

    def __repr__(self):
        return f"<VMUFileEntry {self.name!r} start={self.start_block} size={self.size_blocks}>"


def list_directory(image_bytes):
    """Return a list of VMUFileEntry for every file in this VMU image."""
    root = image_bytes[ROOT_BLOCK * BLOCK:(ROOT_BLOCK + 1) * BLOCK]
    dir_loc = struct.unpack_from("<H", root, 0x4A)[0]
    dir_size = struct.unpack_from("<H", root, 0x4C)[0]
    entries = []
    for i in range(dir_size):
        block_num = dir_loc - i
        block = image_bytes[block_num * BLOCK:(block_num + 1) * BLOCK]
        for e in range(0, BLOCK, 32):
            entry = block[e:e + 32]
            file_type = entry[0]
            if file_type == 0x00:
                continue
            start_block = struct.unpack_from("<H", entry, 2)[0]
            name = entry[4:16].decode("shift_jis", errors="replace").rstrip()
            size_blocks = struct.unpack_from("<H", entry, 0x18)[0]
            saved = _parse_timestamp(entry[0x10:0x18])
            entries.append(VMUFileEntry(file_type, name, start_block, size_blocks, saved))
    return entries


def find_character_file(image_bytes):
    """Find the PSO______SYS entry. Returns a VMUFileEntry or None.
    IMPORTANT: never assume a fixed block number -- a VMU can hold multiple PSO
    files (character SYS, Guild Card list, download-quest data) and their block
    positions vary between images."""
    for entry in list_directory(image_bytes):
        if entry.name == "PSO______SYS":
            return entry
    return None


def get_fat_chain(image_bytes, start_block):
    fat = struct.unpack_from("<256H", image_bytes[254 * BLOCK:255 * BLOCK], 0)
    chain = []
    cur = start_block
    seen = set()
    while True:
        chain.append(cur)
        seen.add(cur)
        nxt = fat[cur]
        if nxt == 0xFFFA or nxt in seen or nxt >= 256:
            break
        cur = nxt
    return chain


def read_file_bytes(image_bytes, start_block):
    """Read the full byte contents (VMS header + payload) of a file starting at
    start_block, following its FAT chain."""
    chain = get_fat_chain(image_bytes, start_block)
    return b"".join(image_bytes[b * BLOCK:(b + 1) * BLOCK] for b in chain), chain


def get_character_data_section(file_bytes):
    """Given the full VMS file bytes (header + icon + encrypted payload), return
    (data_section, data_size, char_file_offset)."""
    num_icons = struct.unpack_from("<H", file_bytes, 0x40)[0]
    data_size = struct.unpack_from("<I", file_bytes, 0x48)[0]
    offset = 0x80 + num_icons * 0x200
    return file_bytes[offset:offset + data_size], data_size, offset


def splice_and_save(image_bytes, chain, offset, new_data_section, save_path):
    """Write new_data_section into file_bytes at `offset`, split back across the
    block chain, and write the resulting full VMU image to save_path."""
    image = bytearray(image_bytes)
    # Rebuild the full file_bytes span covered by this chain, patch, then re-split.
    file_bytes = bytearray(b"".join(image[b * BLOCK:(b + 1) * BLOCK] for b in chain))
    file_bytes[offset:offset + len(new_data_section)] = new_data_section
    pos = 0
    for b in chain:
        image[b * BLOCK:(b + 1) * BLOCK] = file_bytes[pos:pos + BLOCK]
        pos += BLOCK
    with open(save_path, "wb") as f:
        f.write(image)
