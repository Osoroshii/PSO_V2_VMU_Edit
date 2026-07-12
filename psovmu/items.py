"""Item byte encoders/decoders for every item type touched this session.

ItemData raw layout everywhere: data1[12 bytes] + id(u32) + data2[4 bytes].
data1[0] = item class: 0=Weapon 1=Armor/Shield/Unit 2=Mag 3=Tool 4=Meseta
"""
import struct

from . import item_database as db

S_RANK_CHARS = "\0ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_"
S_RANK_SPECIALS = [None, "Jellen", "Zalure", "HP-Revival", "TP-Revival", "Burning",
                   "Tempest", "Blizzard", "Arrest", "Chaos", "Hell", "Spirit",
                   "Berserk", "Demon's", "Gush", "Geist", "King's"]
ATTR_NAMES = {0: None, 1: "Native", 2: "A.Beast", 3: "Machine", 4: "Dark", 5: "Hit"}
TECH_NAMES = ["Foie", "Gifoie", "Rafoie", "Barta", "Gibarta", "Rabarta", "Zonde",
              "Gizonde", "Razonde", "Resta", "Anti", "Reverser", "Shifta", "Deband",
              "Ryuker", "Megid", "Jellen", "Zalure", "Grants"]


def _bswap16(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)


def empty_data2():
    return bytes(4)


# ---------------------------------------------------------------------------
# Weapons (data1[0] = 0)
# ---------------------------------------------------------------------------

def is_s_rank_class(weapon_class):
    return (0x6F < weapon_class < 0x89) or (0xA4 < weapon_class < 0xAA)


def build_weapon(weapon_class, weapon_variant, attr_types_values, grind=0, special=0):
    """attr_types_values: list of up to 3 (type, value) pairs, type 1-5, value int8."""
    data1 = bytearray(12)
    data1[0] = 0x00
    data1[1] = weapon_class
    data1[2] = weapon_variant
    data1[3] = grind
    data1[4] = special
    for i, (t, v) in enumerate(attr_types_values[:3]):
        data1[6 + 2 * i] = t
        data1[7 + 2 * i] = v & 0xFF
    return bytes(data1), empty_data2()


def build_srank_weapon(weapon_class, name, special_index=0, grind=0):
    """NOTE: confirmed against a real save file that a genuine "no custom name"
    S-rank item has ALL-ZERO bytes in the name field (no 0x8000 flag at all) --
    that's what makes the client show the plain type name (e.g. "Needle").
    A custom name we tested in-game ("BFG") encoded per this same algorithm
    displayed as "BFG" followed by garbage "?" characters and could not be
    equipped -- the real client evidently does NOT treat the zero-padded
    trailing character slots as a stop marker the way this (newserv-derived)
    encoding assumes. Until that's root-caused, treat custom S-rank names as
    UNRELIABLE; leaving name="" (the default/safe path below) is confirmed to
    work correctly.

    special_index is ignored (data1[2] is always written as 0) regardless of
    what's passed -- confirmed via real gameplay that a nonzero value there
    makes the client treat the whole item as an unrecognized variant (garbled
    name AND unequippable, same root cause as the name bug above). Kept as a
    parameter only for call-site compatibility; do not resurrect its effect
    without new evidence."""
    name = name.upper()[:8]
    for c in name:
        if c not in S_RANK_CHARS:
            raise ValueError(f"invalid S-rank name character: {c!r} (only A-Z allowed, max 8 chars)")
    data1 = bytearray(12)
    data1[0] = 0x00
    data1[1] = weapon_class
    data1[2] = 0
    data1[3] = grind
    if not name:
        # No custom name: leave the name field entirely zeroed (matches the
        # confirmed-working real-save encoding) rather than setting the
        # "has custom name" flag with empty/garbage character data.
        return bytes(data1), empty_data2()
    idx = [S_RANK_CHARS.index(c) for c in name] + [0] * (8 - len(name))
    w3 = 0x8000 | (idx[1] & 0x1F) | ((idx[0] & 0x1F) << 5)
    w4 = 0x8000 | (idx[4] & 0x1F) | ((idx[3] & 0x1F) << 5) | ((idx[2] & 0x1F) << 10)
    w5 = 0x8000 | (idx[7] & 0x1F) | ((idx[6] & 0x1F) << 5) | ((idx[5] & 0x1F) << 10)
    struct.pack_into("<H", data1, 6, _bswap16(w3))
    struct.pack_into("<H", data1, 8, _bswap16(w4))
    struct.pack_into("<H", data1, 10, _bswap16(w5))
    return bytes(data1), empty_data2()


def decode_weapon(data1):
    weapon_class = data1[1]
    variant = data1[2]
    grind = data1[3]
    if is_s_rank_class(weapon_class):
        special_idx = data1[2]
        special_name = S_RANK_SPECIALS[special_idx] if special_idx < len(S_RANK_SPECIALS) else None
        w3 = _bswap16(struct.unpack_from("<H", data1, 6)[0])
        w4 = _bswap16(struct.unpack_from("<H", data1, 8)[0])
        w5 = _bswap16(struct.unpack_from("<H", data1, 10)[0])
        idxs = [(w3 >> 5) & 0x1F, w3 & 0x1F, (w4 >> 10) & 0x1F, (w4 >> 5) & 0x1F,
                w4 & 0x1F, (w5 >> 10) & 0x1F, (w5 >> 5) & 0x1F, w5 & 0x1F]
        name = ""
        for i in idxs:
            if i == 0:
                break
            name += S_RANK_CHARS[i]
        return {"kind": "weapon", "s_rank": True, "class": weapon_class, "name": name,
                "special": special_name, "grind": grind}
    attrs = []
    for i in range(3):
        t = data1[6 + 2 * i]
        v = struct.unpack_from("<b", data1, 7 + 2 * i)[0]
        if t != 0:
            attrs.append((ATTR_NAMES.get(t, f"?{t}"), v))
    return {"kind": "weapon", "s_rank": False, "class": weapon_class, "variant": variant,
            "grind": grind, "attributes": attrs}


# ---------------------------------------------------------------------------
# Armor / Shields (data1[0] = 1, data1[1] = 1 armor / 2 shield)
# ---------------------------------------------------------------------------

def build_armor_or_shield(is_shield, variant, dfp_bonus, evp_bonus, slots=0):
    data1 = bytearray(12)
    data1[0] = 0x01
    data1[1] = 0x02 if is_shield else 0x01
    data1[2] = variant
    data1[5] = slots
    struct.pack_into("<h", data1, 6, dfp_bonus)
    struct.pack_into("<h", data1, 8, evp_bonus)
    return bytes(data1), empty_data2()


def decode_armor_or_shield(data1):
    is_shield = data1[1] == 2
    variant = data1[2]
    slots = data1[5]
    dfp = struct.unpack_from("<h", data1, 6)[0]
    evp = struct.unpack_from("<h", data1, 8)[0]
    return {"kind": "shield" if is_shield else "armor", "variant": variant,
            "slots": slots, "dfp_bonus": dfp, "evp_bonus": evp}


# ---------------------------------------------------------------------------
# Units (data1[0] = 1, data1[1] = 3)
# ---------------------------------------------------------------------------

def build_unit(variant, modifier=0):
    data1 = bytearray(12)
    data1[0] = 0x01
    data1[1] = 0x03
    data1[2] = variant
    struct.pack_into("<h", data1, 6, modifier)
    return bytes(data1), empty_data2()


def decode_unit(data1):
    variant = data1[2]
    modifier = struct.unpack_from("<h", data1, 6)[0]
    return {"kind": "unit", "variant": variant, "modifier": modifier}


# ---------------------------------------------------------------------------
# Mags (data1[0] = 2) -- genuine V2 bit-packed on-disk format
# ---------------------------------------------------------------------------

def build_mag(species_id, def_l, pow_l, dex_l, mind_l, synchro=120, iq=200, color=0,
              pb_center=0, pb_right=1, pb_left=2):
    def_raw, pow_raw, dex_raw, mind_raw = def_l * 100, pow_l * 100, dex_l * 100, mind_l * 100
    has_center, has_right, has_left = pb_center is not None, pb_right is not None, pb_left is not None
    pb_nums = 0
    if has_center:
        pb_nums |= (pb_center & 0x07)
    if has_right:
        pb_nums |= ((pb_right & 0x07) << 3)
    if has_left:
        pb_nums |= ((pb_left & 0x03) << 6)

    def_w = (def_raw & 0x7FFE) | ((1 if has_right else 0) << 15) | (color & 1)
    pow_w = (pow_raw & 0x7FFE) | ((1 if has_left else 0) << 15) | ((color >> 1) & 1)
    dex_w = (dex_raw & 0xFFFE) | ((color >> 2) & 1)
    mind_w = (mind_raw & 0xFFFE) | ((color >> 3) & 1)

    data1 = bytearray(12)
    data1[0] = 0x02
    data1[1] = species_id
    data1[2] = 200  # level byte -- displayed level is derived from stat sum, this is cosmetic
    data1[3] = pb_nums
    struct.pack_into("<H", data1, 4, def_w)
    struct.pack_into("<H", data1, 6, pow_w)
    struct.pack_into("<H", data1, 8, dex_w)
    struct.pack_into("<H", data1, 10, mind_w)

    data2 = bytearray(4)
    d2w1 = synchro | ((1 if has_center else 0) << 15)
    struct.pack_into("<H", data2, 0, iq)
    struct.pack_into("<H", data2, 2, d2w1)
    return bytes(data1), bytes(data2)


def decode_mag(data1, data2):
    species = data1[1]
    def_w, pow_w, dex_w, mind_w = struct.unpack_from("<4H", data1, 4)
    def_l = (def_w & 0x7FFE) // 100
    pow_l = (pow_w & 0x7FFE) // 100
    dex_l = (dex_w & 0xFFFE) // 100
    mind_l = (mind_w & 0xFFFE) // 100
    level = def_l + pow_l + dex_l + mind_l
    d2w0, d2w1 = struct.unpack_from("<2H", data2, 0)
    iq = d2w0
    synchro = d2w1 & 0x7FFF
    color = (def_w & 1) | ((pow_w & 1) << 1) | ((dex_w & 1) << 2) | ((mind_w & 1) << 3)

    pb_nums = data1[3]
    has_right = bool(def_w & 0x8000)
    has_left = bool(pow_w & 0x8000)
    has_center = bool(d2w1 & 0x8000)
    pb_center = (pb_nums & 0x07) if has_center else None
    pb_right = ((pb_nums >> 3) & 0x07) if has_right else None
    pb_left = ((pb_nums >> 6) & 0x03) if has_left else None

    return {"kind": "mag", "species": species, "level": level,
            "DEF": def_l, "POW": pow_l, "DEX": dex_l, "MIND": mind_l,
            "synchro": synchro, "IQ": iq, "color": color,
            "pb_center": pb_center, "pb_right": pb_right, "pb_left": pb_left}


# ---------------------------------------------------------------------------
# Technique disks (data1[0] = 3, data1[1] = 2)
# ---------------------------------------------------------------------------

def build_tech_disk(tech_id, displayed_level):
    """Direct encoding -- NOT the network-oriented overflow trick (that scheme
    does not apply to local VMU save files; confirmed by empirical testing)."""
    data1 = bytearray(12)
    data1[0] = 0x03
    data1[1] = 0x02
    data1[2] = displayed_level - 1
    data1[4] = tech_id
    return bytes(data1), empty_data2()


def decode_tech_disk(data1):
    level = data1[2] + 1
    tech_id = data1[4]
    name = TECH_NAMES[tech_id] if tech_id < len(TECH_NAMES) else f"?{tech_id}"
    return {"kind": "tech_disk", "technique": name, "tech_id": tech_id, "level": level}


# ---------------------------------------------------------------------------
# Parts / special quest items (data1[0] = 3, data1[1] in {0x0D, 0x0E})
# ---------------------------------------------------------------------------

def build_part(data1_1, data1_2):
    data1 = bytearray(12)
    data1[0] = 0x03
    data1[1] = data1_1
    data1[2] = data1_2
    return bytes(data1), empty_data2()


def decode_part(data1):
    return {"kind": "part", "data1_1": data1[1], "data1_2": data1[2]}


# ---------------------------------------------------------------------------
# Tools / consumables (data1[0] = 3, various data1[1] kinds -- see item_database.TOOLS)
# ---------------------------------------------------------------------------

def build_tool(kind, variant=0, amount=1):
    data1 = bytearray(12)
    data1[0] = 0x03
    data1[1] = kind
    data1[2] = variant
    if db.TOOL_STACKABLE_BY_CODES.get((kind, variant), False):
        data1[5] = amount
    return bytes(data1), empty_data2()


def decode_tool(data1):
    kind = data1[1]
    variant = data1[2]
    stackable = db.TOOL_STACKABLE_BY_CODES.get((kind, variant), False)
    amount = data1[5] if stackable else 1
    return {"kind": "tool_item", "tool_kind": kind, "tool_variant": variant,
            "amount": amount, "stackable": stackable}


# ---------------------------------------------------------------------------
# Generic dispatch
# ---------------------------------------------------------------------------

def decode_item(data1, data2):
    """Best-effort decode of any item's data1/data2 into a human-readable summary."""
    cls = data1[0]
    if cls == 0:
        return decode_weapon(data1)
    if cls == 1:
        sub = data1[1]
        if sub == 3:
            return decode_unit(data1)
        elif sub in (1, 2):
            return decode_armor_or_shield(data1)
        return {"kind": "armor/shield/unit", "raw": data1.hex()}
    if cls == 2:
        return decode_mag(data1, data2)
    if cls == 3:
        if data1[1] == 2:
            return decode_tech_disk(data1)
        if data1[1] in (0x0D, 0x0E):
            return decode_part(data1)
        return decode_tool(data1)
    if cls == 4:
        return {"kind": "meseta"}
    return {"kind": "unknown", "raw": data1.hex()}


def describe_item(data1, data2, amount_override=None):
    """One-line human-readable summary for a table row -- resolves real item
    names from item_database instead of showing raw class/variant hex codes.

    amount_override: bank slots store their stack count in a wrapper field
    outside ItemData entirely (unlike inventory slots, which use data1[5]
    directly) -- pass the bank wrapper's amount here when known, since
    data1[5] is meaningless/zero for bank-stored tools."""
    d = decode_item(data1, data2)
    if amount_override is not None and d.get("kind") == "tool_item":
        d["amount"] = amount_override
    kind = d["kind"]
    if kind == "weapon":
        if d["s_rank"]:
            base_name = db.SRANK_BASE_NAME_BY_CLASS.get(d["class"], f"Unknown S-Rank [{d['class']:#04x}]")
            typed = f' "{d["name"]}"' if d["name"] else ""
            special = f" ({d['special']})" if d["special"] else ""
            return f"{base_name}{typed}{special}"
        name = db.WEAPON_NAME_BY_CLASS_VARIANT.get(
            (d["class"], d["variant"]), f"Unknown Weapon [{d['class']:#04x}/{d['variant']:#04x}]")
        grind = f" +{d['grind']}" if d["grind"] else ""
        attrs = ", ".join(f"{n} {v:+d}%" for n, v in d["attributes"]) if d["attributes"] else "no attributes"
        return f"{name}{grind} ({attrs})"
    if kind == "armor":
        name = db.ARMOR_NAME_BY_VARIANT.get(d["variant"], f"Unknown Armor [{d['variant']:#04x}]")
        slots = f", {d['slots']} slot{'s' if d['slots'] != 1 else ''}" if d["slots"] else ""
        return f"{name} (DEF +{d['dfp_bonus']}, EVP +{d['evp_bonus']}{slots})"
    if kind == "shield":
        name = db.SHIELD_NAME_BY_VARIANT.get(d["variant"], f"Unknown Shield [{d['variant']:#04x}]")
        return f"{name} (DEF +{d['dfp_bonus']}, EVP +{d['evp_bonus']})"
    if kind == "unit":
        name = db.UNIT_NAME_BY_VARIANT.get(d["variant"], f"Unknown Unit [{d['variant']:#04x}]")
        mod = f" {d['modifier']:+d}" if d["modifier"] else ""
        return f"{name}{mod}"
    if kind == "mag":
        name = db.MAG_SPECIES[d["species"]] if d["species"] < len(db.MAG_SPECIES) else f"Unknown species {d['species']}"
        pbs = []
        for slot_name, idx in (("C", d["pb_center"]), ("R", d["pb_right"]), ("L", d["pb_left"])):
            if idx is not None:
                pb_name = db.PB_NAMES[idx] if idx < len(db.PB_NAMES) else f"?{idx}"
                pbs.append(f"{slot_name}:{pb_name}")
        pb_text = f", PB[{', '.join(pbs)}]" if pbs else ""
        return (f"{name} Mag Lv{d['level']} -- "
                f"DEF {d['DEF']}/POW {d['POW']}/DEX {d['DEX']}/MIND {d['MIND']}, "
                f"synchro {d['synchro']}%, IQ {d['IQ']}{pb_text}")
    if kind == "tech_disk":
        return f"{d['technique']} Disk, Lv{d['level']}"
    if kind == "part":
        return db.PART_NAME_BY_CODES.get((d["data1_1"], d["data1_2"]),
                                          f"Unknown Part [{d['data1_1']:#04x}/{d['data1_2']:#04x}]")
    if kind == "tool_item":
        name = db.TOOL_NAME_BY_CODES.get((d["tool_kind"], d["tool_variant"]),
                                          f"Unknown Tool [{d['tool_kind']:#04x}/{d['tool_variant']:#04x}]")
        qty = f" x{d['amount']}" if d["stackable"] else ""
        return f"{name}{qty}"
    if kind == "meseta":
        return "Meseta"
    return f"Unknown item ({d.get('raw', '')})"
