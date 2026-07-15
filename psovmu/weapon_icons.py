"""Extract per-weapon icons from the user's own PSO V2 disc image, the same
way psovmu/mag_icons.py does for mags -- see that module and
docs/REFERENCE.md section 11 for the shared disc/AFS/PVM/PVR groundwork.

/PSO/ITEMKT.AFS also holds one named icon per (mostly-unique-named) weapon,
e.g. "045durandal", "078handgun". The 3-digit prefix is exactly
`real_item_id - ICON_ID_OFFSET`, where `real_item_id` is the item's global ID
in the real item parameter table (`item["ID"]` in
`item-parameter-table-pc-v2.json`) -- confirmed by cross-referencing every
weapon in `item_database.GUNS/SWORDS/WANDS` against that table.

Only 91 of the 206 cataloged weapons have an icon in this set (the rest --
higher-ID guns like the Yasminkov series, and the whole Claw/Double
Saber/Knuckle category added in v0.3.0 straight from the disc's raw PMT
struct, which isn't keyed the same way in the community PMT JSON used here --
aren't present). Rather than guess or substitute a generic per-category icon,
`get_cached_path` returns None for anything not in `_ICON_NUMBER_BY_CLASS_VARIANT`
and the GUI shows "no image for this item", same as an unmapped mag species
would.
"""
import os

from . import disc_extract as de

CACHE_DIR = os.path.expanduser("~/.psovmu_editor_cache/weapon_icons")

# (class, variant) -> ITEMKT.AFS icon number. Generated once against a real
# US V2 disc + item-parameter-table-pc-v2.json; see docs/REFERENCE.md.
# NOTE: the PMT's own JSON keys use UPPERCASE hex for the class/variant pair
# for any class byte containing a letter (a-f) -- e.g. Cane is "000A00", not
# "000a00". Regenerating this table, always look the key up case-sensitively
# matching that convention (see docs/REFERENCE.md) or entire weapon families
# (Cane/Rod/Wand, Claw/Double Saber/Knuckle) silently vanish from coverage.
_ICON_NUMBER_BY_CLASS_VARIANT = {
    (0x01, 0x00): 38, (0x01, 0x01): 39, (0x01, 0x02): 40, (0x01, 0x03): 41,
    (0x01, 0x04): 42, (0x01, 0x05): 43, (0x01, 0x06): 44, (0x01, 0x07): 45,
    (0x02, 0x00): 46, (0x02, 0x01): 47, (0x02, 0x02): 48, (0x02, 0x03): 49,
    (0x02, 0x04): 50, (0x02, 0x05): 51, (0x02, 0x06): 52, (0x02, 0x07): 53,
    (0x03, 0x00): 54, (0x03, 0x01): 55, (0x03, 0x02): 56, (0x03, 0x03): 57,
    (0x03, 0x04): 58, (0x03, 0x05): 59, (0x03, 0x06): 60, (0x03, 0x07): 61,
    (0x04, 0x00): 62, (0x04, 0x01): 63, (0x04, 0x02): 64, (0x04, 0x03): 65,
    (0x04, 0x04): 66, (0x04, 0x05): 67, (0x04, 0x06): 68, (0x04, 0x07): 69,
    (0x05, 0x00): 70, (0x05, 0x01): 71, (0x05, 0x02): 72, (0x05, 0x03): 73,
    (0x05, 0x04): 74, (0x05, 0x05): 75, (0x05, 0x06): 76, (0x05, 0x07): 77,
    (0x06, 0x00): 78, (0x06, 0x01): 79, (0x06, 0x02): 80, (0x06, 0x03): 81,
    (0x06, 0x04): 82, (0x06, 0x05): 83, (0x06, 0x06): 84, (0x06, 0x07): 85,
    (0x07, 0x00): 102, (0x07, 0x01): 103, (0x07, 0x02): 104, (0x07, 0x03): 105,
    (0x07, 0x04): 106, (0x07, 0x05): 107, (0x07, 0x06): 108, (0x07, 0x07): 109,
    (0x08, 0x00): 86, (0x08, 0x01): 87, (0x08, 0x02): 88, (0x08, 0x03): 89,
    (0x08, 0x04): 90, (0x08, 0x05): 91, (0x08, 0x06): 92, (0x08, 0x07): 93,
    (0x09, 0x00): 94, (0x09, 0x01): 95, (0x09, 0x02): 96, (0x09, 0x03): 97,
    (0x09, 0x04): 98, (0x09, 0x05): 99, (0x09, 0x06): 100, (0x09, 0x07): 101,
    (0x0a, 0x00): 110, (0x0a, 0x01): 111, (0x0a, 0x02): 112, (0x0a, 0x03): 113,
    (0x0a, 0x04): 114, (0x0a, 0x05): 115, (0x0a, 0x06): 116,
    (0x0b, 0x00): 117, (0x0b, 0x01): 118, (0x0b, 0x02): 119, (0x0b, 0x03): 120,
    (0x0b, 0x04): 121, (0x0b, 0x05): 122, (0x0b, 0x06): 123,
    (0x0c, 0x00): 124, (0x0c, 0x01): 125, (0x0c, 0x02): 126, (0x0c, 0x03): 127,
    (0x0c, 0x04): 128, (0x0c, 0x05): 129, (0x0c, 0x06): 130,
    (0x0d, 0x00): 131, (0x0d, 0x01): 132,
    (0x0e, 0x00): 134, (0x0e, 0x01): 135, (0x0e, 0x02): 136,
    (0x0f, 0x00): 137, (0x0f, 0x01): 138, (0x0f, 0x02): 139,
    (0x10, 0x01): 142, (0x10, 0x02): 143, (0x10, 0x03): 144, (0x10, 0x04): 145,
    (0x10, 0x05): 146, (0x10, 0x06): 147,
    (0x11, 0x00): 151, (0x11, 0x01): 152,
    (0x12, 0x00): 153,
    (0x13, 0x00): 154,
    (0x14, 0x00): 155,
    (0x15, 0x00): 156,
    (0x1c, 0x00): 163,
    (0x1d, 0x00): 170,
    (0x1e, 0x00): 171,
    (0x1f, 0x00): 172,
    (0x20, 0x00): 164, (0x21, 0x00): 165, (0x22, 0x00): 166, (0x23, 0x00): 167,
    (0x24, 0x00): 168, (0x25, 0x00): 169, (0x26, 0x00): 173,
}


def is_extracted():
    return os.path.isdir(CACHE_DIR) and any(n.endswith(".png") for n in os.listdir(CACHE_DIR))


def get_cached_path(cls, variant):
    if (cls, variant) not in _ICON_NUMBER_BY_CLASS_VARIANT:
        return None
    path = os.path.join(CACHE_DIR, f"{cls:02x}_{variant:02x}.png")
    return path if os.path.exists(path) else None


def extract_all(disc_path, progress=None):
    """Extract every mapped weapon icon from `disc_path` into CACHE_DIR, named
    by (class, variant). `progress(done, total)` is called after each icon if
    given. Returns the count extracted."""
    reader = de.open_disc(disc_path)
    try:
        files = de.list_files(reader)
        raw = de.read_file(reader, files, "ITEMKT.AFS")
    finally:
        reader.close()

    afs_entries = de.parse_afs(raw)
    # Decode every AFS entry once, keyed by its ITEMKT icon number (from the
    # "NNNname" text embedded in its PVM header) -- same extraction approach
    # as mag_icons.extract_all, generalized to look up an arbitrary number
    # rather than assuming a contiguous species range.
    import re
    number_re = re.compile(r"^(\d{3})[a-z]")
    by_number = {}
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
        m = number_re.match(names[0])
        if m:
            by_number[int(m.group(1))] = (dec, tex_start)

    os.makedirs(CACHE_DIR, exist_ok=True)
    done = 0
    total = len(_ICON_NUMBER_BY_CLASS_VARIANT)
    for (cls, variant), icon_num in _ICON_NUMBER_BY_CLASS_VARIANT.items():
        entry = by_number.get(icon_num)
        if entry is None:
            continue
        dec, tex_start = entry
        w, h, rgba = de.decode_pvrt_twiddled(dec[tex_start:], treat_black_as_transparent=True)
        de.write_png(os.path.join(CACHE_DIR, f"{cls:02x}_{variant:02x}.png"), w, h, rgba)
        done += 1
        if progress:
            progress(done, total)
    return done
