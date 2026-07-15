"""Extract mag species icons from the user's own PSO V2 disc image and cache
them locally, so the app never needs network access to show a mag preview.

The icons live in /PSO/ITEMKT.AFS on the disc as small PRS-compressed PVM
containers, one 64x64 twiddled-ARGB4444 PVR texture each, named "magNN" (the
40 non-cell-mag species plus the first 4 cell mags, oddly split by whoever
packed this file at Sonic Team) or "mNN" (the remaining 13 cell mags). Sorting
each group by its numeric suffix and concatenating gives exactly 57 icons in
species_id order (0-56) -- confirmed by visual inspection against known mag
appearances (see docs/REFERENCE.md).
"""
import os
import re

from . import disc_extract as de

CACHE_DIR = os.path.expanduser("~/.psovmu_editor_cache/mag_icons")
EXPECTED_COUNT = 57

_MAG_NAME_RE = re.compile(r"^\d*mag(\d\d)$")
_CELL_NAME_RE = re.compile(r"^m(\d\d)$")


def is_extracted():
    return os.path.isdir(CACHE_DIR) and len(
        [n for n in os.listdir(CACHE_DIR) if n.endswith(".png")]
    ) >= EXPECTED_COUNT


def get_cached_path(species_id):
    path = os.path.join(CACHE_DIR, f"{species_id}.png")
    return path if os.path.exists(path) else None


def extract_all(disc_path, progress=None):
    """Extract all 57 mag icons from `disc_path` (a .cdi or plain ISO) into
    CACHE_DIR, named by species_id. `progress(done, total)` is called after
    each icon if given. Returns the count extracted (always 57 on success).
    Raises disc_extract.DiscFormatError / FileNotFoundError on any mismatch."""
    reader = de.open_disc(disc_path)
    try:
        files = de.list_files(reader)
        raw = de.read_file(reader, files, "ITEMKT.AFS")
    finally:
        reader.close()

    afs_entries = de.parse_afs(raw)
    mag_group, cell_group = [], []
    for off, size in afs_entries:
        if size == 0:
            continue
        try:
            dec = de.prs_decompress(raw[off:off + size])
            parsed = de.parse_pvm(dec)
        except Exception:
            continue
        if not parsed:
            continue
        names, tex_start = parsed
        if len(names) != 1:
            continue
        m = _MAG_NAME_RE.match(names[0])
        if m:
            mag_group.append((int(m.group(1)), dec, tex_start))
            continue
        m = _CELL_NAME_RE.match(names[0])
        if m:
            cell_group.append((int(m.group(1)), dec, tex_start))

    mag_group.sort(key=lambda e: e[0])
    cell_group.sort(key=lambda e: e[0])
    ordered = mag_group + cell_group
    if len(ordered) != EXPECTED_COUNT:
        raise de.DiscFormatError(
            f"expected {EXPECTED_COUNT} mag icons in ITEMKT.AFS (44 'magNN' + 13 'mNN'), "
            f"found {len(mag_group)} + {len(cell_group)} -- this disc doesn't match the "
            "layout this tool was built against"
        )

    os.makedirs(CACHE_DIR, exist_ok=True)
    for species_id, (_, dec, tex_start) in enumerate(ordered):
        w, h, rgba = de.decode_pvrt_twiddled(dec[tex_start:])
        de.write_png(os.path.join(CACHE_DIR, f"{species_id}.png"), w, h, rgba)
        if progress:
            progress(species_id + 1, EXPECTED_COUNT)
    return len(ordered)
