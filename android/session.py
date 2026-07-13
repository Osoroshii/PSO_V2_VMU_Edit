"""A single loaded-and-decrypted VMU character, plus the save-back flow --
ported from the desktop app's App._load_path/_save (main.py in the repo root).
Both vmu_scan.py's folder-preview and main.py's actual editor screen load
through here, so there's exactly one implementation of "decrypt a VMU
character file" and "re-encrypt + verify + splice + confirm" for this app.
"""
import os
import shutil

from psovmu import crypto, vmu


class CharacterSession:
    def __init__(self, path, image_bytes, chain, offset, data_size, serial, dec):
        self.path = path
        self.image_bytes = image_bytes
        self.chain = chain
        self.offset = offset
        self.data_size = data_size
        self.serial = serial
        self.dec = dec  # mutable bytearray of the decrypted character payload

    @classmethod
    def load(cls, path, serial):
        """Raises ValueError (no character in this file) or
        crypto.ChecksumError (wrong serial) on failure -- callers that already
        know the file/serial are good (e.g. opening something the folder scan
        already confirmed) can let those propagate into an error popup; the
        scan itself catches them as "not a real character" instead."""
        with open(path, "rb") as f:
            image_bytes = f.read()
        entry = vmu.find_character_file(image_bytes)
        if entry is None:
            raise ValueError("No character save (PSO______SYS) found in this file.")
        file_bytes, chain = vmu.read_file_bytes(image_bytes, entry.start_block)
        data_section, data_size, offset = vmu.get_character_data_section(file_bytes)
        dec = bytearray(crypto.decrypt_fixed(data_section, data_size, serial))
        return cls(path, image_bytes, chain, offset, data_size, serial, dec)

    def save(self):
        """Re-encrypt, verify the round-trip BEFORE writing anything, splice
        into the full VMU image, write to disk, then re-read fresh from disk
        and decrypt again as a final independent check -- the same "trust
        nothing, verify everything" sequence as the desktop app. Raises on any
        failure; never leaves a partially-written file (the round-trip check
        happens before vmu.splice_and_save is ever called)."""
        backup_path = self.path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(self.path, backup_path)

        reenc = crypto.encrypt_fixed(bytes(self.dec), self.data_size, self.serial)
        if not crypto.verify_round_trip(reenc, self.data_size, self.serial, bytes(self.dec)):
            raise RuntimeError("Round-trip verification failed -- NOT written to disk.")
        vmu.splice_and_save(self.image_bytes, self.chain, self.offset, reenc, self.path)

        with open(self.path, "rb") as f:
            fresh = f.read()
        fresh_file_bytes, _ = vmu.read_file_bytes(fresh, self.chain[0])
        fresh_section, _, _ = vmu.get_character_data_section(fresh_file_bytes)
        crypto.decrypt_fixed(fresh_section, self.data_size, self.serial)  # raises if bad
        self.image_bytes = fresh
