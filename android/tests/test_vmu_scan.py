"""Tests for vmu_scan.scan_folder against the desktop (plain-path) branch of
fileio.py -- covers the three real-world cases the module docstring calls out:
a good character file, a blank/uninitialized VMU slot, and a non-VMU .bin
file (e.g. a BIOS/NVMEM dump) that shouldn't crash the whole folder scan."""
from psovmu import character

from vmu_helpers import build_blank_image, build_vmu_image, make_character_dec
from vmu_scan import scan_folder

SERIAL = 0x4E62F237


def _make_good_character_file(tmp_path, filename, name, class_byte, level):
    dec = make_character_dec()
    character.set_name(dec, name)
    dec[character.SH_BASE + 0x21] = class_byte
    character.set_displayed_level(dec, level)
    (tmp_path / filename).write_bytes(build_vmu_image(dec, SERIAL))


def test_scan_empty_folder_returns_empty_list(tmp_path):
    assert scan_folder(str(tmp_path), SERIAL) == []


def test_scan_none_folder_returns_empty_list():
    assert scan_folder(None, SERIAL) == []


def test_scan_finds_real_character_with_name_class_level(tmp_path):
    _make_good_character_file(tmp_path, "vmu_save_C2.bin", "Osoroshii", 3, 50)

    results = scan_folder(str(tmp_path), SERIAL)

    assert len(results) == 1
    r = results[0]
    assert r.ok is True
    assert r.class_name == "RAmar"
    assert r.level == 50
    assert "Osoroshii" in r.label


def test_scan_reports_blank_vmu_as_not_ok(tmp_path):
    (tmp_path / "vmu_save_D1.bin").write_bytes(build_blank_image())

    results = scan_folder(str(tmp_path), SERIAL)

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error


def test_scan_reports_non_vmu_bin_file_as_not_ok_without_crashing(tmp_path):
    # A plausible non-VMU .bin (e.g. an emulator BIOS/NVMEM dump): same size
    # as a real VMU image, but its bytes have no real directory structure.
    garbage = bytes((i * 7 + 3) % 256 for i in range(256 * 512))
    (tmp_path / "nvmem.bin").write_bytes(garbage)

    results = scan_folder(str(tmp_path), SERIAL)

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error


def test_scan_ignores_non_bin_files(tmp_path):
    (tmp_path / "notes.txt").write_bytes(b"hello")
    assert scan_folder(str(tmp_path), SERIAL) == []


def test_scan_sorts_real_characters_before_failures(tmp_path):
    (tmp_path / "a_blank.bin").write_bytes(build_blank_image())
    _make_good_character_file(tmp_path, "z_real.bin", "Zzz", 4, 10)

    results = scan_folder(str(tmp_path), SERIAL)

    assert [r.ok for r in results] == [True, False]
