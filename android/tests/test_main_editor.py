"""Tests for main.py's PickerScreen and EditorScreen -- the folder-scan/open
flow and the character-field editor, which previously had zero test coverage
(android/tests/ only covered the non-Kivy glue modules session.py/vmu_scan.py/
storage.py/fileio.py)."""
import main as main_mod
from psovmu import character as ch

from vmu_helpers import build_vmu_image, make_character_dec

SERIAL = 0x4E62F237


def _picker(app_screen_manager):
    return app_screen_manager.get_screen("picker")


def _editor(app_screen_manager):
    return app_screen_manager.get_screen("editor")


def _write_character(tmp_path, name="vmu_save_C1.bin", char_name="Osoroshii",
                      class_byte=3, level=50, serial=SERIAL):
    dec = make_character_dec()
    ch.set_name(dec, char_name)
    dec[ch.SH_BASE + 0x21] = class_byte
    ch.set_displayed_level(dec, level)
    path = tmp_path / name
    path.write_bytes(build_vmu_image(dec, serial))
    return str(path)


def test_save_serial_and_rescan_rejects_invalid_serial(app_screen_manager, monkeypatch):
    messages = []
    monkeypatch.setattr(main_mod, "_show_message", lambda title, text: messages.append(title))

    picker = _picker(app_screen_manager)
    picker.serial_input.text = "not hex"
    picker._save_serial_and_rescan()

    assert messages == ["Invalid serial"]
    assert "serial" not in picker.config


def test_rescan_handles_scan_folder_exception_without_crashing(app_screen_manager, monkeypatch, tmp_path):
    """Regression test for the crash fixed alongside this test: rescan() runs
    unconditionally on every return to the picker screen, so a folder whose
    access has gone stale (revoked SAF grant, removed SD card, deleted
    folder) must degrade to a status message instead of raising."""
    picker = _picker(app_screen_manager)
    picker.config["folder"] = str(tmp_path)
    picker.config["serial"] = "4E62F237"

    def _boom(folder, serial):
        raise OSError("permission denied")

    monkeypatch.setattr(main_mod.vmu_scan, "scan_folder", _boom)

    picker.rescan()  # must not raise

    assert "Can't read that folder" in picker.status_label.text


def test_rescan_finds_real_character_and_opens_it_into_the_editor(app_screen_manager, tmp_path):
    path = _write_character(tmp_path, char_name="Osoroshii", class_byte=3, level=50)
    picker = _picker(app_screen_manager)
    picker.config["folder"] = str(tmp_path)
    picker.config["serial"] = f"{SERIAL:X}"

    picker.rescan()

    assert "1 character(s) found of 1 file(s)." == picker.status_label.text
    row = picker.results_box.children[0]
    assert not row.disabled
    row.dispatch("on_release")

    assert app_screen_manager.current == "editor"
    editor = _editor(app_screen_manager)
    assert "Osoroshii" in editor.title_label.text
    assert editor.level_input.text == "50"


def test_open_character_wrong_serial_shows_error_without_crashing(app_screen_manager, monkeypatch, tmp_path):
    path = _write_character(tmp_path, serial=SERIAL)
    messages = []
    monkeypatch.setattr(main_mod, "_show_message", lambda title, text: messages.append(title))

    picker = _picker(app_screen_manager)
    scanned = main_mod.vmu_scan.ScannedVMU(path, "vmu_save_C1.bin", str(tmp_path), True, "Osoroshii")

    picker._open_character(scanned, SERIAL + 1)

    assert messages == ["Can't open"]
    assert app_screen_manager.current == "picker"  # never navigated away


def test_editor_load_session_populates_fields(app_screen_manager, tmp_path):
    path = _write_character(tmp_path, char_name="Kovalev", class_byte=4, level=120)
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL)

    editor = _editor(app_screen_manager)
    editor.load_session(session)

    assert "Kovalev" in editor.title_label.text
    assert "RAcast" in editor.title_label.text
    assert editor.level_input.text == "120"
    assert editor.bank_btn.text == f"Bank (0/{ch.BANK_CAPACITY})"


def test_editor_apply_fields_commits_into_dec(app_screen_manager, tmp_path):
    path = _write_character(tmp_path)
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL)
    editor = _editor(app_screen_manager)
    editor.load_session(session)

    editor.level_input.text = "199"
    editor.exp_input.text = "12345"
    editor.meseta_input.text = "999999"
    editor.stat_inputs["ATP"].text = "1500"

    editor._apply_fields()

    assert ch.get_displayed_level(session.dec) == 199
    assert ch.get_exp(session.dec) == 12345
    assert ch.get_meseta(session.dec) == 999999
    assert ch.get_stats(session.dec)["ATP"] == 1500


def test_editor_sync_to_level_matches_psovmu_character_math(app_screen_manager, tmp_path):
    path = _write_character(tmp_path, class_byte=0, level=10)
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL)
    editor = _editor(app_screen_manager)
    editor.load_session(session)

    editor.level_input.text = "50"
    editor._sync_to_level()

    by_level = ch.cumulative_stats_by_displayed_level(0)
    expected_exp, expected_stats = by_level[50]
    assert editor.exp_input.text == str(expected_exp)
    assert ch.get_displayed_level(session.dec) == 50
    assert ch.get_exp(session.dec) == expected_exp


def test_editor_unlock_flags_sets_every_quest_flag(app_screen_manager, tmp_path):
    path = _write_character(tmp_path)
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL)
    editor = _editor(app_screen_manager)
    editor.load_session(session)

    editor._unlock_flags()

    assert ch.count_quest_flags_set(session.dec) == 0x200 * 8
    assert "4096/4096" in editor.status_label.text


def test_editor_save_success_persists_to_disk(app_screen_manager, tmp_path):
    path = _write_character(tmp_path, name="vmu_save_C1.bin")
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL, name="vmu_save_C1.bin", folder_ref=str(tmp_path))
    editor = _editor(app_screen_manager)
    editor.load_session(session)
    editor.meseta_input.text = "555555"

    editor._save()

    reloaded = CharacterSession.load(path, SERIAL)
    assert ch.get_meseta(reloaded.dec) == 555555


def test_editor_save_failure_shows_message_without_crashing(app_screen_manager, tmp_path, monkeypatch):
    path = _write_character(tmp_path)
    from session import CharacterSession
    session = CharacterSession.load(path, SERIAL)
    messages = []
    monkeypatch.setattr(main_mod, "_show_message", lambda title, text: messages.append(title))
    monkeypatch.setattr(session, "save", lambda: (_ for _ in ()).throw(RuntimeError("disk full")))

    editor = _editor(app_screen_manager)
    editor.load_session(session)

    editor._save()  # must not raise

    assert messages == ["Save failed"]
