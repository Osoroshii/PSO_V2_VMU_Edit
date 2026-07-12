"""Round-trip tests for every item category psovmu.items supports. These are
the same checks done manually during development (see docs/REFERENCE.md and
CHANGELOG.md for the bugs they would have caught -- the S-rank special-index
bug and the Parts name misalignment)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psovmu import items, item_database as db


def test_normal_weapon_round_trip():
    d1, d2 = items.build_weapon(0x1e, 0x00, [(1, 30), (5, 15)], grind=25)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "weapon" and not decoded["s_rank"]
    assert decoded["class"] == 0x1e and decoded["variant"] == 0x00
    assert decoded["grind"] == 25
    assert decoded["attributes"] == [("Native", 30), ("Hit", 15)]


def test_srank_weapon_with_name_round_trip():
    d1, d2 = items.build_srank_weapon(0x72, "TESTNAME", special_index=0, grind=0)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "weapon" and decoded["s_rank"]
    assert decoded["name"] == "TESTNAME"


def test_srank_weapon_blank_name_matches_confirmed_working_pattern():
    # Confirmed against a real save: a genuine "no custom name" S-rank item
    # has the ENTIRE name field zeroed, no 0x8000 flag bits set anywhere.
    d1, d2 = items.build_srank_weapon(0x7f, "", special_index=0, grind=255)
    assert d1.hex() == "007f00ff0000000000000000"


def test_srank_special_index_is_hardcoded_to_zero():
    # data1[2] was confirmed (via real gameplay) to NOT be a usable per-instance
    # special-attack index -- any nonzero value there makes the client treat
    # the item as an unrecognized variant (garbled name, unequippable). The
    # function must ignore special_index entirely, even if a caller passes one.
    d1, _ = items.build_srank_weapon(0x76, "ANYNAME", special_index=5, grind=0)
    assert d1[2] == 0


def test_armor_shield_round_trip():
    d1, d2 = items.build_armor_or_shield(False, 0x17, 10, 10, slots=4)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "armor"
    assert decoded["variant"] == 0x17
    assert decoded["dfp_bonus"] == 10 and decoded["evp_bonus"] == 10
    assert decoded["slots"] == 4


def test_unit_round_trip():
    d1, d2 = items.build_unit(0x1b, 2)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "unit"
    assert decoded["variant"] == 0x1b and decoded["modifier"] == 2


def test_mag_round_trip_with_photon_blasts():
    d1, d2 = items.build_mag(5, 50, 50, 50, 50, synchro=120, iq=200, color=7,
                              pb_center=0, pb_right=2, pb_left=1)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "mag"
    assert decoded["species"] == 5
    assert decoded["level"] == 200
    assert decoded["color"] == 7
    assert decoded["pb_center"] == 0 and decoded["pb_right"] == 2 and decoded["pb_left"] == 1


def test_mag_round_trip_with_no_photon_blasts():
    d1, d2 = items.build_mag(0, 50, 50, 50, 50, pb_center=None, pb_right=None, pb_left=None)
    decoded = items.decode_item(d1, d2)
    assert decoded["pb_center"] is None
    assert decoded["pb_right"] is None
    assert decoded["pb_left"] is None


def test_tech_disk_round_trip():
    d1, d2 = items.build_tech_disk(15, 30)
    decoded = items.decode_item(d1, d2)
    assert decoded["kind"] == "tech_disk"
    assert decoded["technique"] == "Megid"
    assert decoded["level"] == 30


def test_all_parts_round_trip():
    for name, d1v, d2v in db.PARTS:
        d1, d2 = items.build_part(d1v, d2v)
        desc = items.describe_item(d1, d2)
        assert desc == name, f"{name} ({d1v:#04x}/{d2v:#04x}) described as {desc!r}"


def test_all_tools_round_trip():
    for name, d1v, d2v, stackable in db.TOOLS:
        d1, d2 = items.build_tool(d1v, d2v)
        decoded = items.decode_item(d1, d2)
        assert decoded["kind"] == "tool_item"
        assert decoded["stackable"] == stackable
        desc = items.describe_item(d1, d2)
        assert name in desc, f"{name} ({d1v:#04x}/{d2v:#04x}) described as {desc!r}"


def test_tool_bank_amount_override():
    # Real bank-stored tools have data1[5]=0 (the game stores their count in a
    # separate wrapper field, not in the item bytes) -- reproduce that here.
    d1, d2 = items.build_tool(0x09, 0x00, amount=0)  # Scape Doll
    assert items.describe_item(d1, d2) == "Scape Doll x0"
    assert items.describe_item(d1, d2, amount_override=1) == "Scape Doll x1"


def test_no_duplicate_byte_codes_within_parts():
    codes = [(d1, d2) for _, d1, d2 in db.PARTS]
    assert len(codes) == len(set(codes)), "duplicate (d1, d2) codes in PARTS"


def test_no_duplicate_byte_codes_within_tools():
    codes = [(d1, d2) for _, d1, d2, _ in db.TOOLS]
    assert len(codes) == len(set(codes)), "duplicate (d1, d2) codes in TOOLS"
