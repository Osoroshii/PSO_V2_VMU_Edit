"""PSODCV2CharacterFile struct access: name/class/level/stats/exp/quest-flags/bank/inventory.

All offsets are relative to the start of the decrypted 5884-byte payload (i.e. the
`dec` bytes returned by crypto.decrypt_fixed).
"""
import struct
import json
import os

CHAR_BASE = 4  # Character struct starts right after the 4-byte outer checksum
DISP_BASE = CHAR_BASE + 0x034C
VISUAL_BASE = DISP_BASE + 0x24
SH_BASE = VISUAL_BASE + 0x10
QUEST_FLAGS_BASE = CHAR_BASE + 0x0460
BANK_BASE = CHAR_BASE + 0x0660

CLASS_NAMES = ["HUmar", "HUnewearl", "HUcast", "RAmar", "RAcast", "RAcaseal",
               "FOmarl", "FOnewm", "FOnewearl"]
SECTION_ID_NAMES = ["Viridia", "Greenill", "Skyly", "Bluefull", "Purplenum",
                     "Pinkal", "Redria", "Oran", "Yellowboze", "Whitill"]

_LEVEL_TABLE_PATH = os.path.join(os.path.dirname(__file__), "data", "level-table-v1-v2.json")
_level_table_cache = None


def _get_level_table():
    global _level_table_cache
    if _level_table_cache is None:
        with open(_LEVEL_TABLE_PATH) as f:
            _level_table_cache = json.load(f)
    return _level_table_cache


def cumulative_stats_by_displayed_level(class_idx):
    """Returns {displayed_level: (cum_exp, {ATP,MST,EVP,HP,DFP,ATA,LCK})} for a class.
    displayed_level = stored_level + 1 (see get/set_level below)."""
    table = _get_level_table()
    base = table["BaseStats"][class_idx]
    deltas = table["LevelDeltas"][class_idx]
    cum_exp = 0
    cum = dict(base)
    by_level = {}
    for i, d in enumerate(deltas):
        cum_exp += d["EXP"]
        for k in ["ATP", "MST", "EVP", "HP", "DFP", "ATA", "LCK"]:
            cum[k] += d[k]
        by_level[i + 2] = (cum_exp, dict(cum))
    return by_level


def get_max_stats(class_idx):
    return _get_level_table()["MaxStats"][class_idx]


# ---- Basic fields ----

def get_name(dec):
    return dec[VISUAL_BASE:VISUAL_BASE + 0x10].split(b"\x00")[0].decode("ascii", "replace")


def set_name(dec, name):
    raw = name.encode("ascii", "replace")[:16].ljust(16, b"\x00")
    dec[VISUAL_BASE:VISUAL_BASE + 0x10] = raw


def get_class(dec):
    return dec[SH_BASE + 0x21]


def get_class_name(dec):
    c = get_class(dec)
    return CLASS_NAMES[c] if c < len(CLASS_NAMES) else f"?{c}"


def get_section_id(dec):
    return dec[SH_BASE + 0x20]


def get_section_id_name(dec):
    s = get_section_id(dec)
    return SECTION_ID_NAMES[s] if s < len(SECTION_ID_NAMES) else f"?{s}"


def get_stored_level(dec):
    return struct.unpack_from("<I", dec, DISP_BASE + 0x18)[0]


def get_displayed_level(dec):
    """IMPORTANT: the game displays stored_level + 1. Always use this (or
    set_displayed_level) rather than the raw stored value when talking to a user."""
    return get_stored_level(dec) + 1


def set_displayed_level(dec, displayed_level):
    struct.pack_into("<I", dec, DISP_BASE + 0x18, displayed_level - 1)


def get_exp(dec):
    return struct.unpack_from("<I", dec, DISP_BASE + 0x1C)[0]


def set_exp(dec, exp):
    struct.pack_into("<I", dec, DISP_BASE + 0x1C, exp)


def get_meseta(dec):
    return struct.unpack_from("<I", dec, DISP_BASE + 0x20)[0]


def set_meseta(dec, meseta):
    struct.pack_into("<I", dec, DISP_BASE + 0x20, meseta)


def get_stats(dec):
    atp, mst, evp, hp, dfp, ata, lck = struct.unpack_from("<7H", dec, DISP_BASE + 0x00)
    return {"ATP": atp, "MST": mst, "EVP": evp, "HP": hp, "DFP": dfp, "ATA": ata, "LCK": lck}


def set_stats(dec, stats):
    order = ["ATP", "MST", "EVP", "HP", "DFP", "ATA", "LCK"]
    struct.pack_into("<7H", dec, DISP_BASE + 0x00, *[stats[k] for k in order])


def sync_to_level(dec, target_displayed_level, preserve_material_bonus=True):
    """Set EXP and stats (except LCK handling / class quirks) for a target displayed
    level, using the real per-class level table. If preserve_material_bonus is True
    (recommended), keeps whatever bonus the character already has above the pure
    level-table value for each stat (this is how a heavily-played character's
    Material-boosted stats are represented) rather than overwriting to the raw table
    value. Always clamps to the class's absolute MaxStats cap."""
    class_idx = get_class(dec)
    by_level = cumulative_stats_by_displayed_level(class_idx)
    max_stats = get_max_stats(class_idx)
    cur_displayed_level = get_displayed_level(dec)
    cur_stats = get_stats(dec)

    tgt_exp, tgt_table_stats = by_level[target_displayed_level]

    if preserve_material_bonus and cur_displayed_level in by_level:
        _, cur_table_stats = by_level[cur_displayed_level]
        final = {}
        for k in ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]:
            bonus = cur_stats[k] - cur_table_stats[k]
            proposed = tgt_table_stats[k] + bonus
            final[k] = max(0, min(proposed, max_stats[k]))
    else:
        final = {k: min(tgt_table_stats[k], max_stats[k]) for k in
                 ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]}

    set_displayed_level(dec, target_displayed_level)
    set_exp(dec, tgt_exp)
    set_stats(dec, final)
    return final, tgt_exp


# ---- Quest flags ----

def get_quest_flags_raw(dec):
    """Returns the raw 0x200-byte quest flags blob (4 difficulty tables x 0x80 bytes)."""
    return dec[QUEST_FLAGS_BASE:QUEST_FLAGS_BASE + 0x200]


def unlock_all_quest_flags(dec):
    dec[QUEST_FLAGS_BASE:QUEST_FLAGS_BASE + 0x200] = b"\xFF" * 0x200


def count_quest_flags_set(dec):
    return sum(bin(b).count("1") for b in get_quest_flags_raw(dec))


# ---- Bank / Inventory ----

BANK_CAPACITY = 60
INVENTORY_CAPACITY = 30


def get_bank_count(dec):
    return struct.unpack_from("<I", dec, BANK_BASE)[0]


def set_bank_count(dec, n):
    struct.pack_into("<I", dec, BANK_BASE, n)


def get_bank_meseta(dec):
    return struct.unpack_from("<I", dec, BANK_BASE + 4)[0]


def set_bank_meseta(dec, meseta):
    struct.pack_into("<I", dec, BANK_BASE + 4, meseta)


def get_bank_item_raw(dec, slot):
    off = BANK_BASE + 8 + slot * 0x18
    return {
        "data1": bytes(dec[off:off + 12]),
        "id": struct.unpack_from("<I", dec, off + 12)[0],
        "data2": bytes(dec[off + 16:off + 20]),
        "amount": struct.unpack_from("<H", dec, off + 20)[0],
        "present": struct.unpack_from("<H", dec, off + 22)[0],
    }


def set_bank_item_raw(dec, slot, data1, item_id, data2=b"\x00\x00\x00\x00", amount=1, present=1):
    off = BANK_BASE + 8 + slot * 0x18
    dec[off:off + 12] = data1
    struct.pack_into("<I", dec, off + 12, item_id)
    dec[off + 16:off + 20] = data2
    struct.pack_into("<H", dec, off + 20, amount)
    struct.pack_into("<H", dec, off + 22, present)


def clear_bank_slot(dec, slot):
    off = BANK_BASE + 8 + slot * 0x18
    dec[off:off + 24] = b"\x00" * 24


def clear_bank(dec):
    for i in range(BANK_CAPACITY):
        clear_bank_slot(dec, i)
    set_bank_count(dec, 0)


def get_inventory_count(dec):
    return dec[CHAR_BASE]


def set_inventory_count(dec, n):
    dec[CHAR_BASE] = n


def get_inventory_item_raw(dec, slot):
    off = CHAR_BASE + 4 + slot * 0x1C
    return {
        "state": dec[off],
        "flags": struct.unpack_from("<I", dec, off + 4)[0],
        "data1": bytes(dec[off + 8:off + 8 + 12]),
        "id": struct.unpack_from("<I", dec, off + 20)[0],
        "data2": bytes(dec[off + 24:off + 24 + 4]),
    }


def set_inventory_item_raw(dec, slot, data1, item_id, data2=b"\x00\x00\x00\x00", equipped=False):
    off = CHAR_BASE + 4 + slot * 0x1C
    dec[off] = 1  # in inventory
    dec[off + 1] = 0
    dec[off + 2] = 0
    dec[off + 3] = 0
    struct.pack_into("<I", dec, off + 4, 8 if equipped else 0)
    dec[off + 8:off + 8 + 12] = data1
    struct.pack_into("<I", dec, off + 20, item_id)
    dec[off + 24:off + 24 + 4] = data2


def clear_inventory_slot(dec, slot):
    off = CHAR_BASE + 4 + slot * 0x1C
    dec[off:off + 0x1C] = b"\x00" * 0x1C


def clear_inventory(dec):
    for i in range(INVENTORY_CAPACITY):
        clear_inventory_slot(dec, i)
    set_inventory_count(dec, 0)
