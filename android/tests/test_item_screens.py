"""Tests for item_screens.py (ItemListScreen + ItemPickerScreen) -- the actual
touch UI for building/editing Bank/Inventory items, which previously had zero
test coverage despite README.md documenting a real bug here (stale equip-check
text surviving a category switch) that only a manual screenshot caught."""
import item_screens as isc
from psovmu import character as ch
from psovmu import item_database as db
from psovmu import items

from vmu_helpers import build_vmu_image, make_character_dec

SERIAL = 0x4E62F237

# One expected "kind" (from items.decode_item) per category, in CATEGORIES order.
EXPECTED_KIND = {
    "Guns": "weapon", "Swords": "weapon", "Wands": "weapon",
    "Armor": "armor", "Shields": "shield", "Units": "unit", "Mags": "mag",
    "Technique Disks": "tech_disk", "Parts": "part", "Tools": "tool_item",
}


def _picker(app_screen_manager):
    return app_screen_manager.get_screen("item_picker")


def test_switching_category_clears_stale_equip_label(app_screen_manager):
    """Regression test for the bug documented in android/README.md: only the
    weapon/armor/shield/unit builders call _update_equip_label() themselves,
    so switching to a category with no equip check at all (Mags) must still
    clear whatever label text/color the previous category left behind."""
    picker = _picker(app_screen_manager)
    picker.open_for(None, lambda d1, d2: None, char_class_idx=0, return_to="items")
    picker.category_spinner.text = "Guns"
    assert picker.equip_label.text  # Guns has a real equip check -> non-empty

    picker.category_spinner.text = "Mags"
    assert picker.equip_label.text == ""
    assert picker._equip_ok is True


def test_every_category_builds_a_decodable_item(app_screen_manager):
    """Smoke test across all 10 categories -- exactly the kind of indexing
    mistake documented elsewhere in this repo (the Parts-name misalignment in
    docs/REFERENCE.md) would surface here as a wrong 'kind' or a raised
    exception while building the default selection for a category."""
    picker = _picker(app_screen_manager)
    picker.open_for(None, lambda d1, d2: None, char_class_idx=0, return_to="items")
    for cat in isc.CATEGORIES:
        picker.category_spinner.text = cat
        data1, data2 = picker._build_result()
        decoded = items.decode_item(data1, data2)
        assert decoded["kind"] == EXPECTED_KIND[cat], cat


def test_open_for_prefills_existing_weapon(app_screen_manager):
    picker = _picker(app_screen_manager)
    name, stars, wclass, wvariant = db.SWORDS[0]
    data1, data2 = items.build_weapon(wclass, wvariant, [(1, 30)], grind=25)
    existing = items.decode_item(data1, data2)

    picker.open_for(existing, lambda d1, d2: None, char_class_idx=0, return_to="items")

    assert picker.category_spinner.text == db.weapon_category_for_class(wclass)
    assert picker._w["grind"].text == "25"
    rebuilt_data1, rebuilt_data2 = picker._build_result()
    assert items.decode_item(rebuilt_data1, rebuilt_data2) == existing


def test_open_for_prefills_existing_mag(app_screen_manager):
    picker = _picker(app_screen_manager)
    data1, data2 = items.build_mag(3, 50, 50, 50, 50, synchro=100, iq=150, color=5,
                                    pb_center=0, pb_right=1, pb_left=2)
    existing = items.decode_item(data1, data2)

    picker.open_for(existing, lambda d1, d2: None, char_class_idx=0, return_to="items")

    assert picker.category_spinner.text == "Mags"
    assert picker._w["mag_stats"]["DEF"].text == "50"
    assert picker._w["mag_synchro"].text == "100"
    rebuilt_data1, rebuilt_data2 = picker._build_result()
    assert items.decode_item(rebuilt_data1, rebuilt_data2) == existing


def test_confirm_writes_item_and_returns_to_caller_screen(app_screen_manager):
    picker = _picker(app_screen_manager)
    captured = {}

    def on_confirm(data1, data2):
        captured["data1"] = data1
        captured["data2"] = data2

    picker.open_for(None, on_confirm, char_class_idx=0, return_to="items")
    picker.category_spinner.text = "Technique Disks"
    picker._confirm()

    assert "data1" in captured  # on_confirm_cb was actually invoked
    assert items.decode_item(captured["data1"], captured["data2"])["kind"] == "tech_disk"
    assert app_screen_manager.current == "items"


def test_confirm_not_equippable_shows_prompt_but_add_anyway_still_confirms(app_screen_manager, monkeypatch):
    """When check_equip fails, _confirm() must ask via _confirm_popup rather
    than silently blocking or silently allowing -- simulate the user tapping
    "Yes" by making the confirm popup auto-accept."""
    accepted = []
    monkeypatch.setattr(isc, "_confirm_popup", lambda title, text, on_yes: accepted.append(on_yes()))
    monkeypatch.setattr(db, "check_equip", lambda *a, **k: (False, "NOT equippable by this character."))

    picker = _picker(app_screen_manager)
    captured = {}
    picker.open_for(None, lambda d1, d2: captured.setdefault("done", True),
                     char_class_idx=0, return_to="items")
    picker.category_spinner.text = "Guns"

    picker._confirm()

    assert picker._is_not_equippable()
    assert accepted  # the popup's on_yes callback actually ran
    assert captured.get("done") is True


def test_item_list_screen_refresh_reflects_bank_contents(app_screen_manager):
    dec = make_character_dec()
    data1, data2 = items.build_tool(*db.TOOLS[0][1:3])
    ch.set_bank_item_raw(dec, 0, data1, 0x00800000, data2, amount=1)
    ch.set_bank_count(dec, 1)

    class _FakeSession:
        pass

    session = _FakeSession()
    session.dec = dec

    items_screen = app_screen_manager.get_screen("items")
    items_screen.open_for(session, is_bank=True)

    assert items_screen.title_label.text == f"Bank ({1}/{ch.BANK_CAPACITY})"
    first_row_button = items_screen.rows_box.children[-1].children[-1]  # rows_box stacks newest-first
    assert "(empty)" not in first_row_button.text


def test_clear_all_empties_the_bank(app_screen_manager, monkeypatch):
    monkeypatch.setattr(isc, "_confirm_popup", lambda title, text, on_yes: on_yes())
    dec = make_character_dec()
    data1, data2 = items.build_tool(*db.TOOLS[0][1:3])
    ch.set_bank_item_raw(dec, 0, data1, 0x00800000, data2, amount=1)
    ch.set_bank_count(dec, 1)

    class _FakeSession:
        pass

    session = _FakeSession()
    session.dec = dec
    items_screen = app_screen_manager.get_screen("items")
    items_screen.open_for(session, is_bank=True)

    items_screen._clear_all()

    assert ch.get_bank_count(dec) == 0


def test_edit_slot_round_trips_through_the_real_item_picker(app_screen_manager):
    """The full path a user actually drives: tap a bank slot -> item picker
    opens -> confirm -> the chosen item lands back in that exact bank slot."""
    dec = make_character_dec()
    image_path_dec = dec  # kept for clarity; CharacterSession not needed here
    ch.set_bank_count(dec, 0)

    class _FakeSession:
        pass

    session = _FakeSession()
    session.dec = dec

    items_screen = app_screen_manager.get_screen("items")
    items_screen.open_for(session, is_bank=True)

    items_screen._edit_slot(0)  # navigates to "item_picker", pre-fills nothing (empty slot)
    assert app_screen_manager.current == "item_picker"

    picker = app_screen_manager.get_screen("item_picker")
    picker.category_spinner.text = "Parts"
    picker._confirm()

    assert app_screen_manager.current == "items"
    raw = ch.get_bank_item_raw(dec, 0)
    assert items.decode_item(raw["data1"], raw["data2"])["kind"] == "part"
    assert ch.get_bank_count(dec) == 1
