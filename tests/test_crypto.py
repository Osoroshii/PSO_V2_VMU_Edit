"""Round-trip tests for psovmu.crypto -- doesn't need a real save file, just
synthetic buffers, since the encryption/checksum math is self-contained."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psovmu import crypto

SERIAL = 0x12345678


def test_encrypt_decrypt_data_section_round_trip():
    plain = bytes(range(256)) * 4  # 1024 bytes, arbitrary but not all-zero
    enc = crypto.encrypt_data_section(plain, SERIAL)
    dec = crypto.decrypt_data_section(enc, SERIAL)
    assert dec[:len(plain)] == plain


def test_fixed_struct_round_trip():
    size = 64
    plaintext = bytearray(size)
    for i in range(size):
        plaintext[i] = i & 0xFF
    # checksum (offset 0) and round2_seed (last 4 bytes) get overwritten by
    # encrypt_fixed itself, so their initial values here don't matter.
    reenc = crypto.encrypt_fixed(bytes(plaintext), size, SERIAL)
    dec = crypto.decrypt_fixed(reenc, size, SERIAL)
    assert crypto.verify_round_trip(reenc, size, SERIAL, dec)


def test_wrong_serial_raises_checksum_error():
    size = 64
    plaintext = bytes(range(size))
    reenc = crypto.encrypt_fixed(plaintext, size, SERIAL)
    try:
        crypto.decrypt_fixed(reenc, size, SERIAL + 1)
        assert False, "expected ChecksumError for wrong serial"
    except crypto.ChecksumError:
        pass
