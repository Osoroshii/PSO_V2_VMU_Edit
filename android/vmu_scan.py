"""Folder-scanning helpers for the Android app: given a directory of VMU .bin
images and a saved serial number, find every file with a real PSO character in
it and decrypt just enough to show a friendly name/class/level in a picker --
without needing per-file prompts the way the desktop app's single-file-at-a-time
flow does.
"""
import os

from psovmu import character, crypto, vmu


class ScannedVMU:
    def __init__(self, path, ok, label, class_name=None, level=None, error=None):
        self.path = path
        self.ok = ok
        self.label = label
        self.class_name = class_name
        self.level = level
        self.error = error


def _peek_character(path, serial):
    """Best-effort: decrypt just far enough to read name/class/level. Returns
    a ScannedVMU. Never raises -- any failure (not a VMU image, no character
    file, wrong serial) is reported in the result instead."""
    name = os.path.basename(path)
    try:
        with open(path, "rb") as f:
            image_bytes = f.read()
    except OSError as e:
        return ScannedVMU(path, False, name, error=f"can't read file ({e})")

    # Blank/uninitialized VMU images (common for unused emulator slots) and any
    # other non-VMU or corrupted .bin file can fail parsing in ways `vmu.py`
    # doesn't guard against itself (it was only ever fed one user-picked, known-
    # good file at a time before this scan-a-whole-folder feature existed) --
    # anything unexpected here means "not a real character save," not a crash.
    try:
        entry = vmu.find_character_file(image_bytes)
        if entry is None:
            return ScannedVMU(path, False, name, error="no character save in this file")
        file_bytes, _chain = vmu.read_file_bytes(image_bytes, entry.start_block)
        data_section, data_size, _offset = vmu.get_character_data_section(file_bytes)
    except Exception:
        return ScannedVMU(path, False, name, error="not a readable VMU image")

    try:
        dec = bytearray(crypto.decrypt_fixed(data_section, data_size, serial))
    except crypto.ChecksumError:
        return ScannedVMU(path, False, name, error="locked (serial doesn't match)")
    except Exception:
        return ScannedVMU(path, False, name, error="not a readable VMU image")

    char_name = character.get_name(dec).strip() or "(unnamed)"
    class_name = character.get_class_name(dec)
    level = character.get_displayed_level(dec)
    label = f"{char_name} ({class_name}, Lv{level})"
    return ScannedVMU(path, True, label, class_name=class_name, level=level)


def scan_folder(folder_path, serial):
    """Return a list of ScannedVMU, one per *.bin file in folder_path (not
    recursive -- matches how the emulator lays out all VMU slots flat in one
    directory), sorted with real characters first."""
    if not folder_path or not os.path.isdir(folder_path):
        return []
    results = []
    for name in sorted(os.listdir(folder_path)):
        if not name.lower().endswith(".bin"):
            continue
        results.append(_peek_character(os.path.join(folder_path, name), serial))
    results.sort(key=lambda r: (not r.ok, r.label.lower()))
    return results
