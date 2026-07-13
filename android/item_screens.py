"""Bank/Inventory item editing -- ported from the desktop app's AddItemDialog
and App._build_item_tab (../main.py). Two screens: ItemListScreen (the slot
grid for either Bank or Inventory, reused for both via is_bank) and
ItemPickerScreen (the category + fields form for building/editing one item,
equivalent to AddItemDialog).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # for the psovmu/ symlink

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from psovmu import character as ch
from psovmu import item_database as db
from psovmu import items

CATEGORIES = ["Guns", "Swords", "Wands", "Armor", "Shields", "Units", "Mags",
              "Technique Disks", "Parts", "Tools"]
ATTR_CHOICES = ["(none)", "Native", "A.Beast", "Machine", "Dark", "Hit"]


def _show_message(title, text):
    Popup(title=title, content=Label(text=text), size_hint=(0.85, 0.5)).open()


def _confirm_popup(title, text, on_yes):
    content = BoxLayout(orientation="vertical", spacing=8, padding=8)
    content.add_widget(Label(text=text))
    btn_row = BoxLayout(size_hint=(1, None), height=44, spacing=8)
    content.add_widget(btn_row)
    popup = Popup(title=title, content=content, size_hint=(0.85, 0.5))
    yes_btn = Button(text="Yes")
    no_btn = Button(text="Cancel")
    btn_row.add_widget(yes_btn)
    btn_row.add_widget(no_btn)
    yes_btn.bind(on_release=lambda *_: (popup.dismiss(), on_yes()))
    no_btn.bind(on_release=lambda *_: popup.dismiss())
    popup.open()


def _int_field(value=0):
    return TextInput(text=str(value), multiline=False, input_filter="int", input_type="number")


def _row(*widgets, height=44):
    box = BoxLayout(size_hint=(1, None), height=height, spacing=6)
    for w in widgets:
        box.add_widget(w)
    return box


def _label(text, width=70):
    return Label(text=text, size_hint=(None, 1), width=width)


class ItemListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = None
        self.is_bank = True

        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        self.add_widget(root)

        top_row = BoxLayout(size_hint=(1, None), height=40, spacing=8)
        back_btn = Button(text="< Back", size_hint=(None, 1), width=90)
        back_btn.bind(on_release=lambda *_: self._go_back())
        top_row.add_widget(back_btn)
        self.title_label = Label(text="", halign="left", valign="middle")
        self.title_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        top_row.add_widget(self.title_label)
        clear_all_btn = Button(text="Clear All", size_hint=(None, 1), width=100)
        clear_all_btn.bind(on_release=lambda *_: self._clear_all())
        top_row.add_widget(clear_all_btn)
        root.add_widget(top_row)

        self.rows_box = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=4)
        self.rows_box.bind(minimum_height=self.rows_box.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.rows_box)
        root.add_widget(scroll)

    def open_for(self, session, is_bank):
        self.session = session
        self.is_bank = is_bank
        self.refresh()

    def _capacity(self):
        return ch.BANK_CAPACITY if self.is_bank else ch.INVENTORY_CAPACITY

    def _count(self):
        dec = self.session.dec
        return ch.get_bank_count(dec) if self.is_bank else ch.get_inventory_count(dec)

    def _get_raw(self, slot):
        dec = self.session.dec
        return ch.get_bank_item_raw(dec, slot) if self.is_bank else ch.get_inventory_item_raw(dec, slot)

    def refresh(self):
        kind = "Bank" if self.is_bank else "Inventory"
        self.title_label.text = f"{kind} ({self._count()}/{self._capacity()})"
        self.rows_box.clear_widgets()
        count = self._count()
        for slot in range(self._capacity()):
            is_filled = slot < count
            desc = "(empty)"
            if is_filled:
                raw = self._get_raw(slot)
                desc = items.describe_item(raw["data1"], raw["data2"], amount_override=raw.get("amount"))
            item_btn = Button(text=f"{slot}: {desc}", halign="left", shorten=True)
            item_btn.bind(size=lambda w, s: setattr(w, "text_size", s))
            item_btn.bind(on_release=lambda _b, s=slot: self._edit_slot(s))
            clear_btn = Button(text="Clear", size_hint=(None, 1), width=70, disabled=not is_filled)
            clear_btn.bind(on_release=lambda _b, s=slot: self._clear_slot(s))
            self.rows_box.add_widget(_row(item_btn, clear_btn))

    def _edit_slot(self, slot):
        existing = None
        if slot < self._count():
            raw = self._get_raw(slot)
            existing = items.decode_item(raw["data1"], raw["data2"])
            if existing.get("kind") == "tool_item" and existing.get("stackable") and self.is_bank:
                existing["amount"] = raw.get("amount", 1)

        def on_confirm(data1, data2):
            item_id = 0x00800000 + slot
            dec = self.session.dec
            if self.is_bank:
                decoded = items.decode_item(data1, data2)
                amount = decoded["amount"] if decoded.get("kind") == "tool_item" and decoded.get("stackable") else 1
                ch.set_bank_item_raw(dec, slot, data1, item_id, data2, amount=amount)
                ch.set_bank_count(dec, max(ch.get_bank_count(dec), slot + 1))
            else:
                ch.set_inventory_item_raw(dec, slot, data1, item_id, data2)
                ch.set_inventory_count(dec, max(ch.get_inventory_count(dec), slot + 1))
            self.refresh()

        picker = self.manager.get_screen("item_picker")
        picker.open_for(existing, on_confirm, ch.get_class(self.session.dec), return_to="items")
        self.manager.current = "item_picker"

    def _clear_slot(self, slot):
        if self.is_bank:
            ch.clear_bank_slot(self.session.dec, slot)
        else:
            ch.clear_inventory_slot(self.session.dec, slot)
        self.refresh()

    def _clear_all(self):
        kind = "bank" if self.is_bank else "inventory"

        def do_clear():
            if self.is_bank:
                ch.clear_bank(self.session.dec)
            else:
                ch.clear_inventory(self.session.dec)
            self.refresh()

        _confirm_popup("Clear all", f"Clear all {kind} items?", do_clear)

    def _go_back(self):
        self.manager.current = "editor"


class ItemPickerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.on_confirm_cb = None
        self.existing = None
        self.char_class_idx = None
        self.return_to = "items"
        self._w = {}  # this category's field widgets, keyed by name
        self._equip_ok = True

        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        self.add_widget(root)

        top_row = BoxLayout(size_hint=(1, None), height=40, spacing=8)
        cancel_btn = Button(text="Cancel", size_hint=(None, 1), width=90)
        cancel_btn.bind(on_release=lambda *_: self._cancel())
        top_row.add_widget(cancel_btn)
        top_row.add_widget(_label("Category:", width=80))
        self.category_spinner = Spinner(text=CATEGORIES[0], values=CATEGORIES)
        self.category_spinner.bind(text=lambda *_: self._rebuild_body())
        top_row.add_widget(self.category_spinner)
        root.add_widget(top_row)

        self.body_box = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=8, padding=4)
        self.body_box.bind(minimum_height=self.body_box.setter("height"))
        body_scroll = ScrollView(size_hint=(1, 1))
        body_scroll.add_widget(self.body_box)
        root.add_widget(body_scroll)

        self.equip_label = Label(text="", size_hint=(1, None), height=40, halign="left", valign="top")
        self.equip_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.equip_label)

        confirm_btn = Button(text="Add / Update", size_hint=(1, None), height=56, bold=True)
        confirm_btn.bind(on_release=lambda *_: self._confirm())
        root.add_widget(confirm_btn)

    # ---- entry point ----
    def open_for(self, existing, on_confirm, char_class_idx, return_to="items"):
        self.existing = existing
        self.on_confirm_cb = on_confirm
        self.char_class_idx = char_class_idx
        self.return_to = return_to
        cat = CATEGORIES[0]
        if existing:
            kind = existing.get("kind")
            if kind == "weapon":
                cat = db.weapon_category_for_class(existing["class"]) or cat
            else:
                cat = {"armor": "Armor", "shield": "Shields", "unit": "Units", "mag": "Mags",
                       "tech_disk": "Technique Disks", "part": "Parts",
                       "tool_item": "Tools"}.get(kind, cat)
        self.category_spinner.text = cat
        self._rebuild_body()  # spinner.text setter above only fires the binding on a CHANGE

    def _cancel(self):
        self.manager.current = self.return_to

    # ---- body dispatch ----
    def _rebuild_body(self):
        self.body_box.clear_widgets()
        self._w = {}
        # Reset before dispatching -- only the weapon/armor/shield/unit builders
        # call _update_equip_label() themselves (the others have no equip check
        # at all), so without this, switching e.g. Guns -> Mags left the old
        # "Usable by: ..." text on screen for a category it no longer applies to.
        self.equip_label.text = ""
        self._equip_ok = True
        cat = self.category_spinner.text
        if cat == "Guns":
            self._build_weapon_body(db.GUNS, db.GUN_SRANK)
        elif cat == "Swords":
            self._build_weapon_body(db.SWORDS, db.SWORD_SRANK)
        elif cat == "Wands":
            self._build_weapon_body(db.WANDS, db.WAND_SRANK)
        elif cat == "Armor":
            self._build_armor_shield_body(db.ARMOR, is_shield=False)
        elif cat == "Shields":
            self._build_armor_shield_body(db.SHIELDS, is_shield=True)
        elif cat == "Units":
            self._build_unit_body()
        elif cat == "Mags":
            self._build_mag_body()
        elif cat == "Technique Disks":
            self._build_tech_disk_body()
        elif cat == "Parts":
            self._build_part_body()
        elif cat == "Tools":
            self._build_tool_body()

    # ---- Weapon (normal + S-rank) ----
    def _build_weapon_body(self, normal_list, srank_list):
        labels = db.weapon_labels(normal_list)
        srank_labels = [f"[S-Rank] {n}" for c, n in srank_list]
        default_choice = labels[0] if labels else (srank_labels[0] if srank_labels else "")
        existing = self.existing
        if existing and existing.get("kind") == "weapon":
            if existing["s_rank"]:
                srank_name = db.SRANK_BASE_NAME_BY_CLASS.get(existing["class"])
                if srank_name:
                    default_choice = f"[S-Rank] {srank_name}"
            else:
                idx = next((i for i, (n, s, c, v) in enumerate(normal_list)
                            if c == existing["class"] and v == existing["variant"]), None)
                if idx is not None:
                    default_choice = labels[idx]

        spinner = Spinner(text=default_choice, values=labels + srank_labels)
        spinner.bind(text=lambda *_: self._update_equip_label())
        self.body_box.add_widget(_row(_label("Item:"), spinner))
        self._w.update(weapon_spinner=spinner, weapon_normal_list=normal_list,
                        weapon_labels=labels, weapon_srank_list=srank_list)

        grind_default = existing["grind"] if existing and existing.get("kind") == "weapon" else 0
        grind_field = _int_field(grind_default)
        self.body_box.add_widget(_row(_label("Grind:"), grind_field))
        self._w["grind"] = grind_field

        srank_name_default = existing["name"] if existing and existing.get("kind") == "weapon" and existing.get("s_rank") else ""
        srank_name_field = TextInput(text=srank_name_default, multiline=False, hint_text="S-Rank name (max 8 letters, optional)")
        self.body_box.add_widget(_row(_label("S-Rank name:", width=100), srank_name_field))
        self._w["srank_name"] = srank_name_field

        self.body_box.add_widget(Label(text="Attributes (normal weapons only):",
                                        size_hint=(1, None), height=28, halign="left"))
        existing_attrs = existing["attributes"] if (
            existing and existing.get("kind") == "weapon" and not existing.get("s_rank")) else []
        attr_widgets = []
        for i in range(3):
            type_default = existing_attrs[i][0] if i < len(existing_attrs) else "(none)"
            val_default = existing_attrs[i][1] if i < len(existing_attrs) else 30
            type_spinner = Spinner(text=type_default, values=ATTR_CHOICES)
            val_field = _int_field(val_default)
            self.body_box.add_widget(_row(_label(f"Slot {i + 1}:"), type_spinner, val_field))
            attr_widgets.append((type_spinner, val_field))
        self._w["attr_widgets"] = attr_widgets
        self._update_equip_label()

    def _resolve_weapon_class_variant(self):
        spinner = self._w["weapon_spinner"]
        choice = spinner.text
        if choice.startswith("[S-Rank] "):
            name = choice[len("[S-Rank] "):]
            wclass = next(c for c, n in self._w["weapon_srank_list"] if n == name)
            return wclass, 0, True
        idx = self._w["weapon_labels"].index(choice)
        _, _, wclass, wvariant = self._w["weapon_normal_list"][idx]
        return wclass, wvariant, False

    def _confirm_weapon(self):
        wclass, wvariant, is_srank = self._resolve_weapon_class_variant()
        grind = int(self._w["grind"].text or 0)
        if is_srank:
            typed_name = self._w["srank_name"].text.strip()
            # special_idx hardcoded to 0 -- confirmed in-game that any nonzero
            # value here breaks the item (see build_srank_weapon's docstring).
            return items.build_srank_weapon(wclass, typed_name, 0, grind)
        attr_pairs = []
        for type_spinner, val_field in self._w["attr_widgets"]:
            t = type_spinner.text
            if t != "(none)":
                attr_pairs.append((ATTR_CHOICES.index(t), int(val_field.text or 0)))
        return items.build_weapon(wclass, wvariant, attr_pairs, grind=grind)

    # ---- Armor / Shield ----
    def _build_armor_shield_body(self, item_list, is_shield):
        labels = db.item_labels(item_list)
        existing = self.existing
        default_choice = labels[0] if labels else ""
        want_kind = "shield" if is_shield else "armor"
        if existing and existing.get("kind") == want_kind:
            idx = next((i for i, (n, s, v, d, e) in enumerate(item_list)
                        if v == existing["variant"]), None)
            if idx is not None:
                default_choice = labels[idx]

        spinner = Spinner(text=default_choice, values=labels)
        self.body_box.add_widget(_row(_label("Item:"), spinner))
        self._w.update(as_spinner=spinner, as_list=item_list, as_labels=labels, as_is_shield=is_shield)

        dfp_default = existing["dfp_bonus"] if existing and existing.get("kind") == want_kind else 0
        evp_default = existing["evp_bonus"] if existing and existing.get("kind") == want_kind else 0
        slots_default = existing["slots"] if existing and existing.get("kind") == want_kind else 4

        def fill_defaults(*_a):
            idx = labels.index(spinner.text)
            _, _, _, max_dfp, max_evp = item_list[idx]
            self._w["dfp"].text = str(max_dfp)
            self._w["evp"].text = str(max_evp)
            self._update_equip_label()

        dfp_field = _int_field(dfp_default)
        evp_field = _int_field(evp_default)
        self.body_box.add_widget(_row(_label("DEF bonus:"), dfp_field))
        self.body_box.add_widget(_row(_label("EVP bonus:"), evp_field))
        self._w.update(dfp=dfp_field, evp=evp_field)

        if not is_shield:
            slots_field = _int_field(slots_default)
            self.body_box.add_widget(_row(_label("Slots (0-4):"), slots_field))
            self._w["slots"] = slots_field

        spinner.bind(text=fill_defaults)
        if not existing:
            fill_defaults()
        self._update_equip_label()

    def _confirm_armor_shield(self):
        idx = self._w["as_labels"].index(self._w["as_spinner"].text)
        _, _, variant, _, _ = self._w["as_list"][idx]
        slots = int(self._w["slots"].text or 0) if "slots" in self._w else 0
        return items.build_armor_or_shield(self._w["as_is_shield"], variant,
                                            int(self._w["dfp"].text or 0), int(self._w["evp"].text or 0), slots)

    # ---- Unit ----
    def _build_unit_body(self):
        labels = db.item_labels(db.UNITS)
        existing = self.existing
        default_choice = labels[0] if labels else ""
        if existing and existing.get("kind") == "unit":
            idx = next((i for i, (n, s, v, base, mod) in enumerate(db.UNITS)
                        if v == existing["variant"]), None)
            if idx is not None:
                default_choice = labels[idx]

        spinner = Spinner(text=default_choice, values=labels)
        self.body_box.add_widget(_row(_label("Item:"), spinner))
        self._w.update(unit_spinner=spinner, unit_labels=labels)

        modifier_default = existing["modifier"] if existing and existing.get("kind") == "unit" else 2
        modifier_field = _int_field(modifier_default)
        self.body_box.add_widget(_row(_label("Modifier (max +-2):", width=140), modifier_field))
        self._w["modifier"] = modifier_field
        spinner.bind(text=lambda *_: self._update_equip_label())
        self._update_equip_label()

    def _confirm_unit(self):
        idx = self._w["unit_labels"].index(self._w["unit_spinner"].text)
        _, _, variant, _, modamt = db.UNITS[idx]
        modifier = int(self._w["modifier"].text or 0) if modamt > 0 else 0
        return items.build_unit(variant, modifier)

    # ---- Mag ----
    def _build_mag_body(self):
        existing = self.existing if self.existing and self.existing.get("kind") == "mag" else None
        species_names = [f"{name} ({i})" for i, name in enumerate(db.MAG_SPECIES)]
        default_species = species_names[existing["species"]] if existing and existing["species"] < len(species_names) else species_names[0]

        species_spinner = Spinner(text=default_species, values=species_names)
        self.body_box.add_widget(_row(_label("Species:", width=90), species_spinner))
        self._w["species_spinner"] = species_spinner

        stat_fields = {}
        for stat in ["DEF", "POW", "DEX", "MIND"]:
            field = _int_field(existing[stat] if existing else 50)
            self.body_box.add_widget(_row(_label(f"{stat} level:", width=90), field))
            stat_fields[stat] = field
        self._w["mag_stats"] = stat_fields
        self.body_box.add_widget(Label(text="(4 stats should sum to 200 for a maxed mag)",
                                        size_hint=(1, None), height=24, halign="left"))

        synchro_field = _int_field(existing["synchro"] if existing else 120)
        iq_field = _int_field(existing["IQ"] if existing else 200)
        color_field = _int_field(existing["color"] if existing else 0)
        self.body_box.add_widget(_row(_label("Synchro (max 120):", width=140), synchro_field))
        self.body_box.add_widget(_row(_label("IQ (max 200):", width=140), iq_field))
        self.body_box.add_widget(_row(_label("Color (0-15):", width=140), color_field))
        self._w.update(mag_synchro=synchro_field, mag_iq=iq_field, mag_color=color_field)

        self.body_box.add_widget(Label(text="Photon Blasts (a mag can hold up to 3):",
                                        size_hint=(1, None), height=28, halign="left"))
        pb_all = ["(none)"] + db.PB_NAMES
        pb_left_options = ["(none)"] + db.PB_NAMES[:4]  # left slot is only 2 bits on-disk (0-3)

        def pb_default(key, fallback_idx, options):
            if existing:
                idx = existing.get(key)
                val = db.PB_NAMES[idx] if idx is not None else "(none)"
                return val if val in options else "(none)"
            return db.PB_NAMES[fallback_idx] if fallback_idx < len(options) - 1 else "(none)"

        center_spinner = Spinner(text=pb_default("pb_center", 0, pb_all), values=pb_all)
        right_spinner = Spinner(text=pb_default("pb_right", 1, pb_all), values=pb_all)
        left_spinner = Spinner(text=pb_default("pb_left", 2, pb_left_options), values=pb_left_options)
        self.body_box.add_widget(_row(_label("Center PB:", width=90), center_spinner))
        self.body_box.add_widget(_row(_label("Right PB:", width=90), right_spinner))
        self.body_box.add_widget(_row(_label("Left PB (4 opts max):", width=140), left_spinner))
        self._w.update(pb_center=center_spinner, pb_right=right_spinner, pb_left=left_spinner)

    def _confirm_mag(self):
        stat_fields = self._w["mag_stats"]
        total = sum(int(f.text or 0) for f in stat_fields.values())
        if total > 200:
            _show_message("Mag stats", f"Stats sum to {total}, which exceeds the legit max of 200. "
                                        "Clamping proportionally is not automatic -- please adjust.")

        species_names = [f"{name} ({i})" for i, name in enumerate(db.MAG_SPECIES)]
        species_id = species_names.index(self._w["species_spinner"].text)

        def resolve_pb(spinner):
            val = spinner.text
            return None if val == "(none)" else db.PB_NAMES.index(val)

        return items.build_mag(
            species_id,
            int(stat_fields["DEF"].text or 0), int(stat_fields["POW"].text or 0),
            int(stat_fields["DEX"].text or 0), int(stat_fields["MIND"].text or 0),
            int(self._w["mag_synchro"].text or 0), int(self._w["mag_iq"].text or 0),
            int(self._w["mag_color"].text or 0),
            resolve_pb(self._w["pb_center"]), resolve_pb(self._w["pb_right"]), resolve_pb(self._w["pb_left"]))

    # ---- Technique disk ----
    def _build_tech_disk_body(self):
        existing = self.existing if self.existing and self.existing.get("kind") == "tech_disk" else None
        names = [n for n, tid in db.TECHNIQUES]
        default_choice = existing["technique"] if existing and existing["technique"] in names else names[0]

        tech_spinner = Spinner(text=default_choice, values=names)
        level_field = _int_field(existing["level"] if existing else 30)
        self.body_box.add_widget(_row(_label("Technique:", width=90), tech_spinner))
        self.body_box.add_widget(_row(_label("Level (1-30):", width=110), level_field))
        self._w.update(tech_spinner=tech_spinner, tech_level=level_field)

    def _confirm_tech_disk(self):
        names = [n for n, tid in db.TECHNIQUES]
        idx = names.index(self._w["tech_spinner"].text)
        _, tech_id = db.TECHNIQUES[idx]
        return items.build_tech_disk(tech_id, int(self._w["tech_level"].text or 1))

    # ---- Part ----
    def _build_part_body(self):
        existing = self.existing if self.existing and self.existing.get("kind") == "part" else None
        names = [n for n, d1, d2 in db.PARTS]
        default_choice = names[0]
        if existing:
            match = next((n for n, d1, d2 in db.PARTS
                          if d1 == existing["data1_1"] and d2 == existing["data1_2"]), None)
            if match:
                default_choice = match

        part_spinner = Spinner(text=default_choice, values=names)
        self.body_box.add_widget(_row(_label("Part item:", width=90), part_spinner))
        self._w["part_spinner"] = part_spinner

    def _confirm_part(self):
        names = [n for n, d1, d2 in db.PARTS]
        idx = names.index(self._w["part_spinner"].text)
        _, d1, d2 = db.PARTS[idx]
        return items.build_part(d1, d2)

    # ---- Tools ----
    def _build_tool_body(self):
        existing = self.existing if self.existing and self.existing.get("kind") == "tool_item" else None
        names = [n for n, d1, d2, stackable in db.TOOLS]
        default_choice = names[0]
        if existing:
            match = next((n for n, d1, d2, stackable in db.TOOLS
                          if d1 == existing["tool_kind"] and d2 == existing["tool_variant"]), None)
            if match:
                default_choice = match

        tool_spinner = Spinner(text=default_choice, values=names)
        amount_default = existing["amount"] if existing and existing.get("stackable") else 1
        amount_field = _int_field(amount_default)

        def update_amount_state(*_a):
            idx = names.index(tool_spinner.text)
            _, _, _, stackable = db.TOOLS[idx]
            amount_field.disabled = not stackable

        tool_spinner.bind(text=update_amount_state)
        self.body_box.add_widget(_row(_label("Tool item:", width=90), tool_spinner))
        self.body_box.add_widget(_row(_label("Amount:", width=90), amount_field))
        self._w.update(tool_spinner=tool_spinner, tool_amount=amount_field)
        update_amount_state()

    def _confirm_tool(self):
        names = [n for n, d1, d2, stackable in db.TOOLS]
        idx = names.index(self._w["tool_spinner"].text)
        _, d1, d2, stackable = db.TOOLS[idx]
        amount = int(self._w["tool_amount"].text or 1) if stackable else 1
        return items.build_tool(d1, d2, amount)

    # ---- Equip check (weapons/armor/shields/units only) ----
    def _update_equip_label(self):
        self._equip_ok = True  # default: no equip-check applies to this category
        cat = self.category_spinner.text
        try:
            if cat in ("Guns", "Swords", "Wands"):
                wclass, wvariant, is_srank = self._resolve_weapon_class_variant()
                if is_srank:
                    self.equip_label.text = ""
                    return
                ok, msg = db.check_equip(self.char_class_idx, 0, wclass, wvariant)
            elif cat in ("Armor", "Shields"):
                idx = self._w["as_labels"].index(self._w["as_spinner"].text)
                _, _, variant, _, _ = self._w["as_list"][idx]
                kind_byte = 0x02 if self._w["as_is_shield"] else 0x01
                ok, msg = db.check_equip(self.char_class_idx, 1, kind_byte, variant)
            elif cat == "Units":
                idx = self._w["unit_labels"].index(self._w["unit_spinner"].text)
                _, _, variant, _, _ = db.UNITS[idx]
                ok, msg = db.check_equip(self.char_class_idx, 1, 0x03, variant)
            else:
                self.equip_label.text = ""
                return
        except Exception:
            self.equip_label.text = ""
            return
        self.equip_label.text = msg
        self.equip_label.color = (1, 1, 1, 1) if ok else (1, 0.4, 0.4, 1)
        self._equip_ok = ok

    def _is_not_equippable(self):
        return not self._equip_ok

    # ---- confirm dispatch ----
    def _build_result(self):
        cat = self.category_spinner.text
        builders = {
            "Guns": self._confirm_weapon, "Swords": self._confirm_weapon, "Wands": self._confirm_weapon,
            "Armor": self._confirm_armor_shield, "Shields": self._confirm_armor_shield,
            "Units": self._confirm_unit, "Mags": self._confirm_mag,
            "Technique Disks": self._confirm_tech_disk, "Parts": self._confirm_part,
            "Tools": self._confirm_tool,
        }
        return builders[cat]()

    def _confirm(self):
        def do_confirm():
            try:
                data1, data2 = self._build_result()
            except Exception as e:
                _show_message("Error building item", str(e))
                return
            self.on_confirm_cb(data1, data2)
            self.manager.current = self.return_to

        if self._is_not_equippable():
            _confirm_popup(
                "Not equippable",
                self.equip_label.text + "\n\nAdd it anyway? (it will sit in the "
                "slot but the game will refuse to equip it)",
                do_confirm)
        else:
            do_confirm()
