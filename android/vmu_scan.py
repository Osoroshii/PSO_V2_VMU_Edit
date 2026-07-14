"""Folder-scanning helpers for the Android app: given a directory of VMU .bin
images and a saved serial number, find every file with a real PSO character in
it and decrypt just enough to show a friendly name/class/level in a picker --
without needing per-file prompts the way the desktop app's single-file-at-a-time
flow does.

File access goes through fileio.py, not os.listdir()/open() directly, so this
works the same whether folder_path is a plain directory (desktop) or an
Android Storage Access Framework tree URI (see fileio.py's module docstring).
"""
from psovmu import character, crypto

import fileio
from session import CharacterSession


class ScannedVMU:
    def __init__(self, path, name, folder_ref, ok, label, class_name=None, level=None, error=None):
        self.path = path
        self.name = name
        self.folder_ref = folder_ref
        self.ok = ok
        self.label = label
        self.class_name = class_name
        self.level = level
        self.error = error


def _peek_character(path, name, folder_ref, serial):
    """Best-effort: decrypt just far enough to read name/class/level. Returns
    a ScannedVMU. Never raises -- any failure (not a VMU image, no character
    file, wrong serial) is reported in the result instead.

    Blank/uninitialized VMU images (common for unused emulator slots) and any
    other non-VMU or corrupted .bin file can fail parsing in ways `vmu.py`
    doesn't guard against itself (it was only ever fed one user-picked, known-
    good file at a time before this scan-a-whole-folder feature existed) --
    anything unexpected here means "not a real character save," not a crash.
    """
    try:
        session = CharacterSession.load(path, serial, name=name, folder_ref=folder_ref)
    except (OSError, ValueError) as e:
        return ScannedVMU(path, name, folder_ref, False, name, error=str(e) or "no character save in this file")
    except crypto.ChecksumError:
        return ScannedVMU(path, name, folder_ref, False, name, error="locked (serial doesn't match)")
    except Exception:
        return ScannedVMU(path, name, folder_ref, False, name, error="not a readable VMU image")

    dec = session.dec
    char_name = character.get_name(dec).strip() or "(unnamed)"
    class_name = character.get_class_name(dec)
    level = character.get_displayed_level(dec)
    label = f"{char_name} ({class_name}, Lv{level})"
    return ScannedVMU(path, name, folder_ref, True, label, class_name=class_name, level=level)


def scan_folder(folder_ref, serial):
    """Return a list of ScannedVMU, one per *.bin file directly in
    folder_ref (not recursive -- matches how the emulator lays out all VMU
    slots flat in one directory), sorted with real characters first."""
    if not folder_ref:
        return []
    results = [
        _peek_character(file_ref, name, folder_ref, serial)
        for name, file_ref in fileio.list_dir_bin_files(folder_ref)
    ]
    results.sort(key=lambda r: (not r.ok, r.label.lower()))
    return results
