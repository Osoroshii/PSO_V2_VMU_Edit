"""PSO Dreamcast V2 save encryption (round1 = disc/account serial, round2 = embedded seed).

Validated against real VMU save files during reverse-engineering; see the reference
notes at /Volumes/MacEMU/bios/dc/PSO Saves/ClaudeVMUWork/ for full derivation.
"""
import struct
import zlib
import random


class PSOV2Encryption:
    STREAM_LENGTH = 0x38

    def __init__(self, seed):
        self.stream = [0] * (self.STREAM_LENGTH + 1)
        self.end_offset = self.STREAM_LENGTH
        seed &= 0xFFFFFFFF
        a, b = 1, seed
        self.stream[0x37] = b
        vi = 0x15
        while vi <= 0x36 * 0x15:
            self.stream[vi % 0x37] = a
            c = (b - a) & 0xFFFFFFFF
            b = a
            a = c
            vi += 0x15
        for _ in range(5):
            self.update_stream()

    def update_stream(self):
        for z in range(1, 0x19):
            self.stream[z] = (self.stream[z] - self.stream[z + 0x1F]) & 0xFFFFFFFF
        for z in range(0x19, 0x38):
            self.stream[z] = (self.stream[z] - self.stream[z - 0x18]) & 0xFFFFFFFF
        self.offset = 1

    def next(self):
        if self.offset == self.end_offset:
            self.update_stream()
        v = self.stream[self.offset]
        self.offset += 1
        return v

    def encrypt_minus(self, data):
        n = len(data) // 4
        for x in range(n):
            val = struct.unpack_from("<I", data, x * 4)[0]
            struct.pack_into("<I", data, x * 4, (self.next() - val) & 0xFFFFFFFF)

    def encrypt_xor(self, data):
        n = len(data) // 4
        for x in range(n):
            val = struct.unpack_from("<I", data, x * 4)[0]
            struct.pack_into("<I", data, x * 4, val ^ self.next())


class ShuffleTables:
    def __init__(self, crypt):
        self.forward_table = list(range(0x100))
        self.reverse_table = [0] * 0x100
        r28 = 0xFF
        r31 = 0xFF
        while r28 >= 0:
            r3 = self.pseudorand(crypt, r28 + 1)
            t = self.forward_table[r3]
            self.forward_table[r3] = self.forward_table[r31]
            self.forward_table[r31] = t
            self.reverse_table[t] = r28
            r31 -= 1
            r28 -= 1

    @staticmethod
    def pseudorand(crypt, prev):
        return (((prev & 0xFFFF) * ((crypt.next() >> 16) & 0xFFFF)) >> 16) & 0xFFFF

    def shuffle(self, src, reverse):
        table = self.reverse_table if reverse else self.forward_table
        size = len(src)
        dest = bytearray(size)
        full = size & 0xFFFFFF00
        for bo in range(0, full, 0x100):
            for z in range(0x100):
                dest[bo + table[z]] = src[bo + z]
        rs = full
        rl = size & 0xFF
        dest[rs:rs + rl] = src[rs:rs + rl]
        return bytes(dest)


def encrypt_data_section(plain, round1_seed):
    buf = bytearray(plain)
    pad = (-len(buf)) % 4
    if pad:
        buf += b"\x00" * pad
    PSOV2Encryption(round1_seed).encrypt_minus(buf)
    shuf = ShuffleTables(PSOV2Encryption(round1_seed))
    return shuf.shuffle(bytes(buf), False)[:len(plain)]


def decrypt_data_section(data_section, round1_seed):
    shuf = ShuffleTables(PSOV2Encryption(round1_seed))
    dec = bytearray(shuf.shuffle(data_section, True))
    PSOV2Encryption(round1_seed).encrypt_minus(dec)
    return bytes(dec)


class ChecksumError(Exception):
    """Raised when a decrypted struct's checksum doesn't match -- almost always
    means the serial number is wrong."""
    pass


def decrypt_fixed(data_section, struct_size, round1_seed):
    """Decrypt a fixed-size struct (e.g. PSODCV2CharacterFile, 5884 bytes).
    Raises ChecksumError if the serial number appears to be wrong."""
    dec = bytearray(decrypt_data_section(data_section, round1_seed)[:struct_size])
    round2_seed = struct.unpack_from("<I", dec, struct_size - 4)[0]
    portion = bytearray(dec[:struct_size - 4])
    PSOV2Encryption(round2_seed).encrypt_xor(portion)
    dec[:struct_size - 4] = portion
    checksum = struct.unpack_from("<I", dec, 0)[0]
    dec[0:4] = b"\x00" * 4
    actual = zlib.crc32(bytes(dec[:struct_size])) & 0xFFFFFFFF
    dec[0:4] = struct.pack("<I", checksum)
    if checksum != actual:
        raise ChecksumError(
            f"Checksum mismatch (expected 0x{checksum:08x}, got 0x{actual:08x}) -- "
            "the serial number is probably wrong for this file."
        )
    return bytes(dec)


def encrypt_fixed(plaintext_struct, struct_size, round1_seed):
    """Inverse of decrypt_fixed. Picks a fresh random round2_seed each call --
    this is normal/expected, matching what the real game does."""
    buf = bytearray(plaintext_struct)
    buf[0:4] = b"\x00" * 4
    r2seed = random.randrange(0, 0x100000000)
    struct.pack_into("<I", buf, struct_size - 4, r2seed)
    checksum = zlib.crc32(bytes(buf[:struct_size])) & 0xFFFFFFFF
    struct.pack_into("<I", buf, 0, checksum)
    portion = bytearray(buf[:struct_size - 4])
    PSOV2Encryption(r2seed).encrypt_xor(portion)
    buf[:struct_size - 4] = portion
    return encrypt_data_section(bytes(buf), round1_seed)


def verify_round_trip(reencrypted, struct_size, round1_seed, expected_plaintext):
    """Decrypt what was just encrypted and confirm it matches, ignoring the
    checksum/round2_seed fields (which legitimately get fresh values each time)."""
    check_dec = decrypt_fixed(reencrypted, struct_size, round1_seed)
    a = bytearray(check_dec)
    a[0:4] = b"\x00" * 4
    a[-4:] = b"\x00" * 4
    b = bytearray(expected_plaintext)
    b[0:4] = b"\x00" * 4
    b[-4:] = b"\x00" * 4
    return bytes(a) == bytes(b)
