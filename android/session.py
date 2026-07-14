"""A single loaded-and-decrypted VMU character, plus the save-back flow --
ported from the desktop app's App._load_path/_save (main.py in the repo root).
Both vmu_scan.py's folder-preview and main.py's actual editor screen load
through here, so there's exactly one implementation of "decrypt a VMU
character file" and "re-encrypt + verify + splice + confirm" for this app.

File access goes through fileio.py rather than open()/shutil directly, so
this works unchanged whether `path`/`folder_ref` are plain filesystem paths
(desktop) or Android Storage Access Framework URIs (see fileio.py's module
docstring for why that split exists).
"""
from psovmu import crypto, vmu

import fileio


class CharacterSession:
    def __init__(self, path, name, folder_ref, image_bytes, chain, offset, data_size, serial, dec):
        self.path = path
        self.name = name  # display name (basename on desktop, SAF document name on Android)
        self.folder_ref = folder_ref  # needed only for the Android backup-file path
        self.image_bytes = image_bytes
        self.chain = chain
        self.offset = offset
        self.data_size = data_size
        self.serial = serial
        self.dec = dec  # mutable bytearray of the decrypted character payload

    @classmethod
    def load(cls, path, serial, name=None, folder_ref=None):
        """Raises ValueError (no character in this file) or
        crypto.ChecksumError (wrong serial) on failure -- callers that already
        know the file/serial are good (e.g. opening something the folder scan
        already confirmed) can let those propagate into an error popup; the
        scan itself catches them as "not a real character" instead.

        name/folder_ref are only needed for save()'s backup step on Android
        (a SAF sibling file has to be created within the parent tree, not
        just addressed by a "path + suffix" string) -- desktop callers can
        omit them."""
        image_bytes = fileio.read_bytes(path)
        entry = vmu.find_character_file(image_bytes)
        if entry is None:
            raise ValueError("No character save (PSO______SYS) found in this file.")
        file_bytes, chain = vmu.read_file_bytes(image_bytes, entry.start_block)
        data_section, data_size, offset = vmu.get_character_data_section(file_bytes)
        dec = bytearray(crypto.decrypt_fixed(data_section, data_size, serial))
        return cls(path, name, folder_ref, image_bytes, chain, offset, data_size, serial, dec)

    def save(self):
        """Re-encrypt, verify the round-trip BEFORE writing anything, splice
        into the full VMU image, write to disk, then re-read fresh from disk
        and decrypt again as a final independent check -- the same "trust
        nothing, verify everything" sequence as the desktop app. Raises on any
        failure; never leaves a partially-written file (the round-trip check
        happens before any write)."""
        backup_name = (self.name or "character") + ".bak"
        fileio.ensure_backup(self.folder_ref, self.path, backup_name)

        reenc = crypto.encrypt_fixed(bytes(self.dec), self.data_size, self.serial)
        if not crypto.verify_round_trip(reenc, self.data_size, self.serial, bytes(self.dec)):
            raise RuntimeError("Round-trip verification failed -- NOT written to disk.")
        spliced = vmu.splice(self.image_bytes, self.chain, self.offset, reenc)
        fileio.write_bytes(self.path, spliced)

        fresh = fileio.read_bytes(self.path)
        fresh_file_bytes, _ = vmu.read_file_bytes(fresh, self.chain[0])
        fresh_section, _, _ = vmu.get_character_data_section(fresh_file_bytes)
        crypto.decrypt_fixed(fresh_section, self.data_size, self.serial)  # raises if bad
        self.image_bytes = fresh
