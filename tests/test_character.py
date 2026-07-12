"""Tests for psovmu.character -- uses a synthetic zeroed buffer sized like a
real decrypted character struct rather than a real save file (no personal
save data is bundled with the repo)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from psovmu import character as ch

# Real decrypted character payloads are 5884 bytes; a bit of headroom is fine.
BUF_SIZE = 6000


def make_dec():
    return bytearray(BUF_SIZE)


def test_level_is_stored_zero_indexed():
    dec = make_dec()
    ch.set_displayed_level(dec, 200)
    assert ch.get_stored_level(dec) == 199
    assert ch.get_displayed_level(dec) == 200


def test_stats_round_trip():
    dec = make_dec()
    stats = {"ATP": 1264, "MST": 0, "EVP": 751, "HP": 864, "DFP": 606, "ATA": 1541, "LCK": 100}
    ch.set_stats(dec, stats)
    assert ch.get_stats(dec) == stats


def test_bank_item_round_trip():
    dec = make_dec()
    data1 = bytes(range(12))
    data2 = bytes([0xAA, 0xBB, 0xCC, 0xDD])
    ch.set_bank_item_raw(dec, 5, data1, 0x00800005, data2, amount=3, present=1)
    raw = ch.get_bank_item_raw(dec, 5)
    assert raw["data1"] == data1
    assert raw["data2"] == data2
    assert raw["id"] == 0x00800005
    assert raw["amount"] == 3
    assert raw["present"] == 1


def test_inventory_item_round_trip():
    dec = make_dec()
    data1 = bytes(range(12))
    ch.set_inventory_item_raw(dec, 2, data1, 0x00800002)
    raw = ch.get_inventory_item_raw(dec, 2)
    assert raw["data1"] == data1
    assert raw["state"] == 1


def test_clear_bank_slot():
    dec = make_dec()
    ch.set_bank_item_raw(dec, 5, bytes(range(12)), 0x00800005, amount=3)
    ch.clear_bank_slot(dec, 5)
    raw = ch.get_bank_item_raw(dec, 5)
    assert raw["present"] == 0
    assert raw["data1"] == bytes(12)


def test_unlock_all_quest_flags():
    dec = make_dec()
    assert ch.count_quest_flags_set(dec) == 0
    ch.unlock_all_quest_flags(dec)
    assert ch.count_quest_flags_set(dec) == 0x200 * 8


def test_sync_to_level_matches_table_with_no_material_bonus():
    dec = make_dec()
    class_idx = 0  # HUmar
    by_level = ch.cumulative_stats_by_displayed_level(class_idx)
    start_level = 10
    _, start_stats = by_level[start_level]
    ch.set_displayed_level(dec, start_level)
    ch.set_stats(dec, {k: start_stats[k] for k in ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]})

    target_level = 50
    final, exp = ch.sync_to_level(dec, target_level, preserve_material_bonus=True)
    _, expected_table_stats = by_level[target_level]
    for k in ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]:
        assert final[k] == expected_table_stats[k], k
    assert ch.get_displayed_level(dec) == target_level
    assert ch.get_exp(dec) == exp


def test_sync_to_level_preserves_material_bonus():
    dec = make_dec()
    class_idx = 0
    by_level = ch.cumulative_stats_by_displayed_level(class_idx)
    start_level = 10
    _, start_stats = by_level[start_level]
    bonus = 5
    ch.set_displayed_level(dec, start_level)
    boosted = {k: start_stats[k] + bonus for k in ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]}
    ch.set_stats(dec, boosted)

    target_level = 50
    final, _ = ch.sync_to_level(dec, target_level, preserve_material_bonus=True)
    _, table_stats = by_level[target_level]
    max_stats = ch.get_max_stats(class_idx)
    for k in ["ATP", "MST", "EVP", "DFP", "ATA", "LCK", "HP"]:
        expected = min(table_stats[k] + bonus, max_stats[k])
        assert final[k] == expected, k
