"""Tests for session.CharacterSession against the desktop (plain-path) branch
of fileio.py -- synthetic VMU images only, built with vmu_helpers."""
from psovmu import character, crypto

from session import CharacterSession
from vmu_helpers import build_blank_image, build_vmu_image, make_character_dec

SERIAL = 0x4E62F237


def _write(tmp_path, image_bytes, name="vmu_save_C1.bin"):
    path = tmp_path / name
    path.write_bytes(image_bytes)
    return str(path)


def test_load_reads_back_name_class_level(tmp_path):
    dec = make_character_dec()
    character.set_name(dec, "Osoroshii")
    dec[character.SH_BASE + 0x21] = 3  # RAmar
    character.set_displayed_level(dec, 50)
    image = build_vmu_image(dec, SERIAL)
    path = _write(tmp_path, image)

    session = CharacterSession.load(path, SERIAL)

    assert character.get_name(session.dec) == "Osoroshii"
    assert character.get_class_name(session.dec) == "RAmar"
    assert character.get_displayed_level(session.dec) == 50


def test_load_wrong_serial_raises_checksum_error(tmp_path):
    dec = make_character_dec()
    image = build_vmu_image(dec, SERIAL)
    path = _write(tmp_path, image)

    try:
        CharacterSession.load(path, SERIAL + 1)
        assert False, "expected ChecksumError for wrong serial"
    except crypto.ChecksumError:
        pass


def test_load_blank_image_raises_value_error(tmp_path):
    path = _write(tmp_path, build_blank_image())

    try:
        CharacterSession.load(path, SERIAL)
        assert False, "expected ValueError (no character file) for a blank VMU"
    except ValueError:
        pass


def test_save_round_trip_persists_edits_and_makes_backup(tmp_path):
    dec = make_character_dec()
    character.set_name(dec, "Kovalev")
    character.set_meseta(dec, 1000)
    image = build_vmu_image(dec, SERIAL)
    path = _write(tmp_path, image)

    session = CharacterSession.load(path, SERIAL, name="vmu_save_C1.bin", folder_ref=str(tmp_path))
    character.set_meseta(session.dec, 999999)
    character.set_displayed_level(session.dec, 150)
    session.save()

    backup_path = tmp_path / "vmu_save_C1.bin.bak"
    assert backup_path.exists()
    backup_session = CharacterSession.load(str(backup_path), SERIAL)
    assert character.get_meseta(backup_session.dec) == 1000  # pre-edit value

    reloaded = CharacterSession.load(path, SERIAL)
    assert character.get_meseta(reloaded.dec) == 999999
    assert character.get_displayed_level(reloaded.dec) == 150
    assert character.get_name(reloaded.dec) == "Kovalev"


def test_save_does_not_overwrite_existing_backup(tmp_path):
    dec = make_character_dec()
    character.set_meseta(dec, 111)
    path = _write(tmp_path, build_vmu_image(dec, SERIAL))
    session = CharacterSession.load(path, SERIAL, name="vmu_save_C1.bin", folder_ref=str(tmp_path))
    character.set_meseta(session.dec, 222)
    session.save()

    # A second edit + save should leave the backup (first-ever pre-edit state)
    # untouched -- matches the desktop app's os.path.exists-guarded backup.
    character.set_meseta(session.dec, 333)
    session.save()

    backup_session = CharacterSession.load(str(tmp_path / "vmu_save_C1.bin.bak"), SERIAL)
    assert character.get_meseta(backup_session.dec) == 111
