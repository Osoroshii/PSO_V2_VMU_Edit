"""Builds minimal synthetic VMU images for android/tests/ -- no real save files
are bundled with the repo (see tests/test_character.py at the repo root for the
same convention). Only fills in the directory/FAT/root-block fields that
psovmu.vmu actually reads; everything else is left zeroed.
"""
import struct

from psovmu import crypto

BLOCK = 512
TOTAL_BLOCKS = 256
FAT_BLOCK = 254
DIR_BLOCK = 253
ROOT_BLOCK = 255

# Real decrypted character payloads are 5884 bytes; a bit of headroom is fine
# (matches tests/test_character.py's BUF_SIZE) so every psovmu.character
# offset used by vmu_scan.py's name/class/level preview is in bounds.
CHARACTER_SIZE = 6000


def make_character_dec():
    return bytearray(CHARACTER_SIZE)


def build_vmu_image(dec, serial, filename="PSO______SYS", start_block=1):
    """Build a full 256-block VMU image containing one file (named `filename`,
    normally "PSO______SYS") holding the encrypted form of `dec`. Uses a 0-icon
    VMS header (num_icons=0) so the payload starts right after the fixed 0x80
    header -- no icon bitmap needed for anything psovmu.vmu/session.py reads."""
    data_size = len(dec)
    encrypted = crypto.encrypt_fixed(bytes(dec), data_size, serial)

    header = bytearray(0x80)
    struct.pack_into("<H", header, 0x40, 0)  # num_icons
    struct.pack_into("<I", header, 0x48, data_size)
    file_bytes = bytes(header) + encrypted

    size_blocks = (len(file_bytes) + BLOCK - 1) // BLOCK
    padded = file_bytes.ljust(size_blocks * BLOCK, b"\x00")

    image = bytearray(TOTAL_BLOCKS * BLOCK)
    for i in range(size_blocks):
        b = start_block + i
        image[b * BLOCK:(b + 1) * BLOCK] = padded[i * BLOCK:(i + 1) * BLOCK]

    # FAT chain: each block points to the next; the last uses the real
    # end-of-chain marker psovmu.vmu.get_fat_chain looks for (0xFFFA).
    fat = [0] * (TOTAL_BLOCKS)
    for i in range(size_blocks):
        b = start_block + i
        fat[b] = (start_block + i + 1) if i < size_blocks - 1 else 0xFFFA
    image[FAT_BLOCK * BLOCK:(FAT_BLOCK + 1) * BLOCK] = struct.pack("<256H", *fat)

    # One directory entry, occupying the first 32 bytes of a single dir block.
    entry = bytearray(32)
    entry[0] = 0x33  # any nonzero file type ("game data", per the VMU spec)
    name_bytes = filename.encode("ascii").ljust(12, b" ")[:12]
    entry[4:16] = name_bytes
    struct.pack_into("<H", entry, 2, start_block)
    struct.pack_into("<H", entry, 0x18, size_blocks)
    image[DIR_BLOCK * BLOCK:DIR_BLOCK * BLOCK + 32] = entry

    # Root block: point at the FAT/directory blocks above (dir grows
    # downward from DIR_BLOCK, 1 block is enough for a single entry).
    root = bytearray(BLOCK)
    struct.pack_into("<H", root, 0x46, FAT_BLOCK)
    struct.pack_into("<H", root, 0x4A, DIR_BLOCK)
    struct.pack_into("<H", root, 0x4C, 1)
    image[ROOT_BLOCK * BLOCK:(ROOT_BLOCK + 1) * BLOCK] = root

    return bytes(image)


def build_blank_image():
    """An all-zero image: root block's own dir_size reads as 0, so
    find_character_file finds nothing -- matches an unused emulator VMU slot."""
    return bytes(TOTAL_BLOCKS * BLOCK)
