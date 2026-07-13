#!/usr/bin/env python3
"""PSO V2 VMU Character/Item Editor -- MVP.

Drag a VMU .bin file onto the window (or use File > Open), enter the disc/account
serial number when prompted, then edit the character's level/stats/quest-flags and
bank/inventory items. Save writes back to the same file (a .bak backup of the
original is created alongside it the first time you save).
"""
import json
import os
import shutil
import struct
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

from psovmu import vmu, crypto, character as ch, items, item_database as db

CONFIG_PATH = os.path.expanduser("~/.psovmu_editor_config.json")


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f)
    except OSError:
        pass  # best-effort -- losing the remembered serial isn't worth crashing over


def _activate_app():
    """Ask macOS directly to make this process the frontmost app.

    Tk's focus_force() only operates within Tk's own notion of focus -- it
    doesn't reliably make a freshly-shown window the true OS-level key window.
    Symptom this fixes: a dialog LOOKS focused and typing into a text field
    works, but the first click on a button does nothing (the click is consumed
    by macOS just to activate/raise the app) until a second interaction (e.g.
    pressing Enter) proves the window is now actually key."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to set frontmost of first process '
             f'whose unix id is {os.getpid()} to true'],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass


def _force_to_front(win, focus_widget=None):
    """macOS/tkinter sometimes opens a new Toplevel behind the main window or
    without keyboard focus -- if that Toplevel is modal (grab_set), the app then
    looks completely hung (spinning wheel) because input is blocked to an unseen
    window. Always call this right after creating a modal dialog, before grab_set.

    Deliberately does NOT use `-topmost`: forcing a window topmost fights macOS's
    own window-manager-driven focus handling once the user starts dragging the
    title bar, which was causing focus to be lost mid-drag and never recovered.
    `transient()` (set by the caller) plus a single lift()/focus_force() is enough
    to bring a dialog to front and keep it correctly tied to its parent."""
    _activate_app()
    win.deiconify()
    win.lift()
    win.focus_force()
    if focus_widget is not None:
        win.after_idle(focus_widget.focus_set)


def _center_on_parent(win, parent):
    """Center a Toplevel over its parent so the user never needs to drag it just
    to see or reach it -- dragging a modal dialog was itself the trigger for the
    focus-loss bug this replaces."""
    win.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    ww, wh = win.winfo_reqwidth(), win.winfo_reqheight()
    x = px + max((pw - ww) // 2, 0)
    y = py + max((ph - wh) // 2, 0)
    win.geometry(f"+{x}+{y}")


class SerialDialog(tk.Toplevel):
    """Custom modal dialog (not tkinter.simpledialog.Dialog) so we have full
    control over the show/focus sequence -- see _force_to_front above."""

    def __init__(self, parent, error_message=None, default_serial=None):
        super().__init__(parent)
        self.title("Enter disc/account serial number")
        self.result_serial = None
        self.resizable(False, False)

        body = tk.Frame(self, padx=12, pady=12)
        body.pack(fill="both", expand=True)

        row = 0
        if error_message:
            tk.Label(body, text=error_message, fg="red", wraplength=320, justify="left").grid(
                row=row, column=0, columnspan=2, pady=(0, 10), sticky="w")
            row += 1

        tk.Label(body, text="Serial number (hex, e.g. 4E62F237):").grid(row=row, column=0, sticky="w")
        self.entry = tk.Entry(body, width=20)
        self.entry.grid(row=row, column=1, padx=(6, 0))
        self.entry.bind("<Return>", lambda e: self._ok())
        if default_serial:
            # Pre-fill with the last-used serial (most people reuse the same disc/
            # account repeatedly) and select it so typing immediately overwrites it
            # if a different serial is actually needed this time.
            self.entry.insert(0, default_serial)
            self.entry.select_range(0, tk.END)
        row += 1

        btns = tk.Frame(body)
        btns.grid(row=row, column=0, columnspan=2, pady=(12, 0))
        tk.Button(btns, text="OK", command=self._ok, width=10, default="active").pack(side="left", padx=4)
        tk.Button(btns, text="Cancel", command=self._cancel, width=10).pack(side="left", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.transient(parent)
        _center_on_parent(self, parent)
        _force_to_front(self, self.entry)
        self.grab_set()
        self.wait_window(self)

    def _ok(self):
        val = self.entry.get().strip().replace("0x", "").replace("0X", "")
        try:
            self.result_serial = int(val, 16)
        except ValueError:
            messagebox.showerror("Invalid serial", "Enter a hex serial number, e.g. 4E62F237.", parent=self)
            return
        self.destroy()

    def _cancel(self):
        self.result_serial = None
        self.destroy()

    def apply(self):
        val = self.entry.get().strip().replace("0x", "").replace("0X", "")
        try:
            self.result_serial = int(val, 16)
        except ValueError:
            self.result_serial = None


class AddItemDialog(tk.Toplevel):
    """Dialog for building a new item to place in a bank/inventory slot."""
    CATEGORIES = ["Guns", "Swords", "Wands", "Armor", "Shields", "Units", "Mags",
                  "Technique Disks", "Parts", "Tools"]

    def __init__(self, parent, on_confirm, existing=None, char_class_idx=None):
        """existing: optional (data1, data2) of the item already in the target
        slot -- when given, the dialog opens on that item's category with all
        fields pre-filled from its current values, so a single detail (e.g. an
        attribute %) can be tweaked without re-specifying the whole item.
        char_class_idx: the loaded character's class (0-8), used to warn if the
        selected item isn't actually equippable by this character/race/gender
        combo per the real item parameter table (e.g. androids can't use some
        S-rank weapons, Force-only canes can't go on a Hunter, etc.)."""
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.result = None  # (data1, data2)
        self.char_class_idx = char_class_idx
        self._existing = None
        existing_category = None
        if existing is not None:
            data1, data2 = existing
            self._existing = items.decode_item(data1, data2)
            kind = self._existing["kind"]
            if kind == "weapon":
                existing_category = db.weapon_category_for_class(self._existing["class"])
            else:
                existing_category = {"armor": "Armor", "shield": "Shields", "unit": "Units",
                                      "mag": "Mags", "tech_disk": "Technique Disks",
                                      "part": "Parts", "tool_item": "Tools"}.get(kind)

        self.title("Edit Item" if existing_category else "Add Item")

        tk.Label(self, text="Category:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.category_var = tk.StringVar(value=existing_category or self.CATEGORIES[0])
        cat_menu = ttk.Combobox(self, textvariable=self.category_var, values=self.CATEGORIES, state="readonly")
        cat_menu.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        cat_menu.bind("<<ComboboxSelected>>", lambda e: self._on_category_changed())

        self.body_frame = tk.Frame(self)
        self.body_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)

        btns = tk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, pady=8)
        tk.Button(btns, text="Add / Update", command=self._confirm).pack(side="left", padx=4)
        tk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self._rebuild_body()

        self.transient(parent)
        _center_on_parent(self, parent)
        _force_to_front(self)
        self.grab_set()

    def _clear_body(self):
        for w in self.body_frame.winfo_children():
            w.destroy()

    def _on_category_changed(self):
        # Switching category means starting a fresh item -- the pre-filled
        # existing values no longer correspond to what's now selected.
        self._existing = None
        self._rebuild_body()

    def _rebuild_body(self):
        self._clear_body()
        # Categories without their own equip-check label (Mags, Technique Disks,
        # Parts) must not inherit a stale reference from whatever category was
        # selected before -- _confirm()'s equip_label check would then hit a
        # destroyed widget and raise, silently aborting the Add/Update click.
        if hasattr(self, "equip_label"):
            del self.equip_label
        cat = self.category_var.get()
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
        self._weapon_normal_list = normal_list
        self._weapon_srank_list = srank_list
        self._weapon_labels = db.weapon_labels(normal_list)
        names = self._weapon_labels + [f"[S-Rank] {n}" for c, n in srank_list]

        existing = self._existing if self._existing and self._existing["kind"] == "weapon" else None
        default_choice = names[0]
        if existing:
            if existing["s_rank"]:
                srank_name = db.SRANK_BASE_NAME_BY_CLASS.get(existing["class"])
                if srank_name:
                    default_choice = f"[S-Rank] {srank_name}"
            else:
                idx = next((i for i, (n, s, c, v) in enumerate(normal_list)
                            if c == existing["class"] and v == existing["variant"]), None)
                if idx is not None:
                    default_choice = self._weapon_labels[idx]

        tk.Label(self.body_frame, text="Item:").grid(row=0, column=0, sticky="w")
        self.weapon_choice = tk.StringVar(value=default_choice)
        combo = ttk.Combobox(self.body_frame, textvariable=self.weapon_choice, values=names,
                              state="readonly", width=40)
        combo.grid(row=0, column=1, sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda e: self._update_weapon_fields())

        self.grind_var = tk.IntVar(value=existing["grind"] if existing else 0)
        tk.Label(self.body_frame, text="Grind:").grid(row=1, column=0, sticky="w")
        tk.Spinbox(self.body_frame, from_=0, to=99, textvariable=self.grind_var, width=6).grid(row=1, column=1, sticky="w")

        tk.Label(self.body_frame, text="Attributes (normal weapons only):").grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.attr_vars = []
        attr_choices = ["(none)", "Native", "A.Beast", "Machine", "Dark", "Hit"]
        existing_attrs = existing["attributes"] if existing and not existing["s_rank"] else []
        for i in range(3):
            tk.Label(self.body_frame, text=f"Slot {i+1}:").grid(row=3+i, column=0, sticky="w")
            frame = tk.Frame(self.body_frame)
            frame.grid(row=3+i, column=1, sticky="w")
            if i < len(existing_attrs):
                type_var = tk.StringVar(value=existing_attrs[i][0])
                val_var = tk.IntVar(value=existing_attrs[i][1])
            else:
                type_var = tk.StringVar(value="(none)")
                val_var = tk.IntVar(value=30)
            ttk.Combobox(frame, textvariable=type_var, values=attr_choices, state="readonly", width=10).pack(side="left")
            tk.Spinbox(frame, from_=-99, to=99, textvariable=val_var, width=5).pack(side="left", padx=(4, 0))
            self.attr_vars.append((type_var, val_var))

        tk.Label(self.body_frame, text="S-Rank custom name (max 8 letters, optional -- confirmed working"
                 " in-game, shows as \"NAME TYPE\", e.g. \"TESTNAME RIFLE\"):").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.srank_name_var = tk.StringVar(value=existing["name"] if existing and existing["s_rank"] else "")
        tk.Entry(self.body_frame, textvariable=self.srank_name_var, width=10).grid(row=7, column=0, sticky="w")

        tk.Label(self.body_frame, text="S-Rank special: CONFIRMED BROKEN in-game (any nonzero value here\n"
                 "makes the client treat the item as an unrecognized variant -- \"?\" name,\n"
                 "cannot equip). Locked to (none) until a real fix is found.",
                 fg="#a00", justify="left").grid(row=7, column=1, sticky="w")
        self.srank_special_var = tk.StringVar(value="(none)")
        ttk.Combobox(self.body_frame, textvariable=self.srank_special_var, values=["(none)"],
                     state="disabled", width=12).grid(row=8, column=1, sticky="w")

        self.equip_label = tk.Label(self.body_frame, text="", wraplength=380, justify="left", font=("", 10, "bold"))
        self.equip_label.grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._update_weapon_fields()

    def _resolve_weapon_class_variant(self):
        choice = self.weapon_choice.get()
        if choice.startswith("[S-Rank] "):
            name_lookup = choice[len("[S-Rank] "):]
            wclass = next(c for c, n in self._weapon_srank_list if n == name_lookup)
            return wclass, 0
        idx = self._weapon_labels.index(choice)
        _, _, wclass, wvariant = self._weapon_normal_list[idx]
        return wclass, wvariant

    def _update_weapon_fields(self):
        try:
            wclass, wvariant = self._resolve_weapon_class_variant()
            ok, msg = db.check_equip(self.char_class_idx, 0, wclass, wvariant)
        except Exception:
            ok, msg = True, ""
        self.equip_label.config(text=msg, fg="black" if ok else "red")

    def _confirm_weapon(self):
        choice = self.weapon_choice.get()
        grind = self.grind_var.get()
        if choice.startswith("[S-Rank] "):
            name_lookup = choice[len("[S-Rank] "):]
            wclass = next(c for c, n in self._weapon_srank_list if n == name_lookup)
            # Leave blank if the user didn't type a name -- do NOT default to the
            # category name. A confirmed-working real item has the name field
            # entirely zeroed out (shows the plain type name in-game); a custom
            # name is currently confirmed to render as garbage + block equip, so
            # don't force every S-rank item down that path by default.
            typed_name = self.srank_name_var.get().strip()
            # special_idx hardcoded to 0 -- confirmed in-game that any nonzero
            # value here breaks the item (see label above / reference doc).
            return items.build_srank_weapon(wclass, typed_name, 0, grind)
        else:
            idx = self._weapon_labels.index(choice)
            name, stars, wclass, wvariant = self._weapon_normal_list[idx]
            attr_pairs = []
            for type_var, val_var in self.attr_vars:
                t = type_var.get()
                if t != "(none)":
                    type_num = ["(none)", "Native", "A.Beast", "Machine", "Dark", "Hit"].index(t)
                    attr_pairs.append((type_num, val_var.get()))
            return items.build_weapon(wclass, wvariant, attr_pairs, grind=grind)

    # ---- Armor / Shield ----
    def _build_armor_shield_body(self, item_list, is_shield):
        self._as_list = item_list
        self._as_is_shield = is_shield
        self._as_labels = db.item_labels(item_list)
        names = self._as_labels

        want_kind = "shield" if is_shield else "armor"
        existing = self._existing if self._existing and self._existing["kind"] == want_kind else None
        default_choice = names[0]
        if existing:
            idx = next((i for i, (n, s, v, d, e) in enumerate(item_list) if v == existing["variant"]), None)
            if idx is not None:
                default_choice = self._as_labels[idx]

        tk.Label(self.body_frame, text="Item:").grid(row=0, column=0, sticky="w")
        self.as_choice = tk.StringVar(value=default_choice)
        combo = ttk.Combobox(self.body_frame, textvariable=self.as_choice, values=names, state="readonly", width=40)
        combo.grid(row=0, column=1, sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda e: self._on_as_choice_changed())

        tk.Label(self.body_frame, text="DEF bonus:").grid(row=1, column=0, sticky="w")
        self.as_dfp_var = tk.IntVar(value=existing["dfp_bonus"] if existing else 0)
        tk.Spinbox(self.body_frame, from_=-99, to=999, textvariable=self.as_dfp_var, width=6).grid(row=1, column=1, sticky="w")

        tk.Label(self.body_frame, text="EVP bonus:").grid(row=2, column=0, sticky="w")
        self.as_evp_var = tk.IntVar(value=existing["evp_bonus"] if existing else 0)
        tk.Spinbox(self.body_frame, from_=-99, to=999, textvariable=self.as_evp_var, width=6).grid(row=2, column=1, sticky="w")

        if not is_shield:
            tk.Label(self.body_frame, text="Slots (0-4):").grid(row=3, column=0, sticky="w")
            self.as_slots_var = tk.IntVar(value=existing["slots"] if existing else 4)
            tk.Spinbox(self.body_frame, from_=0, to=4, textvariable=self.as_slots_var, width=6).grid(row=3, column=1, sticky="w")
        else:
            self.as_slots_var = tk.IntVar(value=0)

        self.equip_label = tk.Label(self.body_frame, text="", wraplength=380, justify="left", font=("", 10, "bold"))
        self.equip_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        if not existing:
            self._fill_as_defaults()
        self._update_as_equip_label()

    def _fill_as_defaults(self):
        idx = self._as_labels.index(self.as_choice.get())
        _, _, _, max_dfp, max_evp = self._as_list[idx]
        self.as_dfp_var.set(max_dfp)
        self.as_evp_var.set(max_evp)

    def _on_as_choice_changed(self):
        self._fill_as_defaults()
        self._update_as_equip_label()

    def _update_as_equip_label(self):
        idx = self._as_labels.index(self.as_choice.get())
        _, _, variant, _, _ = self._as_list[idx]
        kind_byte = 0x02 if self._as_is_shield else 0x01
        ok, msg = db.check_equip(self.char_class_idx, 1, kind_byte, variant)
        self.equip_label.config(text=msg, fg="black" if ok else "red")

    def _confirm_armor_shield(self):
        idx = self._as_labels.index(self.as_choice.get())
        _, _, variant, _, _ = self._as_list[idx]
        return items.build_armor_or_shield(self._as_is_shield, variant, self.as_dfp_var.get(),
                                            self.as_evp_var.get(), self.as_slots_var.get())

    # ---- Unit ----
    def _build_unit_body(self):
        self._unit_labels = db.item_labels(db.UNITS)
        names = self._unit_labels
        existing = self._existing if self._existing and self._existing["kind"] == "unit" else None
        default_choice = names[0]
        if existing:
            idx = next((i for i, (n, s, v, base, modamt) in enumerate(db.UNITS)
                        if v == existing["variant"]), None)
            if idx is not None:
                default_choice = self._unit_labels[idx]

        tk.Label(self.body_frame, text="Item:").grid(row=0, column=0, sticky="w")
        self.unit_choice = tk.StringVar(value=default_choice)
        combo = ttk.Combobox(self.body_frame, textvariable=self.unit_choice, values=names, state="readonly", width=40)
        combo.grid(row=0, column=1, sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda e: self._update_unit_equip_label())

        tk.Label(self.body_frame, text="Modifier (legit max is +2):").grid(row=1, column=0, sticky="w")
        self.unit_modifier_var = tk.IntVar(value=existing["modifier"] if existing else 2)
        tk.Spinbox(self.body_frame, from_=-2, to=2, textvariable=self.unit_modifier_var, width=6).grid(row=1, column=1, sticky="w")

        self.equip_label = tk.Label(self.body_frame, text="", wraplength=380, justify="left", font=("", 10, "bold"))
        self.equip_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._update_unit_equip_label()

    def _update_unit_equip_label(self):
        idx = self._unit_labels.index(self.unit_choice.get())
        _, _, variant, _, _ = db.UNITS[idx]
        ok, msg = db.check_equip(self.char_class_idx, 1, 0x03, variant)
        self.equip_label.config(text=msg, fg="black" if ok else "red")

    def _confirm_unit(self):
        idx = self._unit_labels.index(self.unit_choice.get())
        _, _, variant, base, modamt = db.UNITS[idx]
        modifier = self.unit_modifier_var.get() if modamt > 0 else 0
        return items.build_unit(variant, modifier)

    # ---- Mag ----
    def _build_mag_body(self):
        existing = self._existing if self._existing and self._existing["kind"] == "mag" else None

        def pb_default(key, fallback_idx):
            if existing:
                idx = existing.get(key)
                return db.PB_NAMES[idx] if idx is not None else "(none)"
            return db.PB_NAMES[fallback_idx]

        species_names = [f"{name} ({i})" for i, name in enumerate(db.MAG_SPECIES)]
        default_species = species_names[existing["species"]] if existing and existing["species"] < len(species_names) else species_names[0]

        tk.Label(self.body_frame, text="Species:").grid(row=0, column=0, sticky="w")
        self.mag_species_var = tk.StringVar(value=default_species)
        ttk.Combobox(self.body_frame, textvariable=self.mag_species_var, values=species_names,
                     state="readonly", width=28).grid(row=0, column=1, sticky="w")

        stat_vars = {}
        for i, stat in enumerate(["DEF", "POW", "DEX", "MIND"]):
            tk.Label(self.body_frame, text=f"{stat} level:").grid(row=1+i, column=0, sticky="w")
            v = tk.IntVar(value=existing[stat] if existing else 50)
            tk.Spinbox(self.body_frame, from_=0, to=200, textvariable=v, width=6).grid(row=1+i, column=1, sticky="w")
            stat_vars[stat] = v
        self.mag_stat_vars = stat_vars
        tk.Label(self.body_frame, text="(4 stats should sum to 200 for a maxed mag)", fg="gray").grid(
            row=5, column=0, columnspan=2, sticky="w")

        tk.Label(self.body_frame, text="Synchro (max 120):").grid(row=6, column=0, sticky="w")
        self.mag_synchro_var = tk.IntVar(value=existing["synchro"] if existing else 120)
        tk.Spinbox(self.body_frame, from_=0, to=120, textvariable=self.mag_synchro_var, width=6).grid(row=6, column=1, sticky="w")

        tk.Label(self.body_frame, text="IQ (max 200):").grid(row=7, column=0, sticky="w")
        self.mag_iq_var = tk.IntVar(value=existing["IQ"] if existing else 200)
        tk.Spinbox(self.body_frame, from_=0, to=200, textvariable=self.mag_iq_var, width=6).grid(row=7, column=1, sticky="w")

        tk.Label(self.body_frame, text="Color (0-15):").grid(row=8, column=0, sticky="w")
        self.mag_color_var = tk.IntVar(value=existing["color"] if existing else 0)
        tk.Spinbox(self.body_frame, from_=0, to=15, textvariable=self.mag_color_var, width=6).grid(row=8, column=1, sticky="w")

        tk.Label(self.body_frame, text="Photon Blasts (a mag can hold up to 3):",
                 font=("", 10, "bold")).grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))

        pb_all = ["(none)"] + db.PB_NAMES
        pb_left_options = ["(none)"] + db.PB_NAMES[:4]  # left slot is only 2 bits on-disk (0-3)

        tk.Label(self.body_frame, text="Center PB:").grid(row=10, column=0, sticky="w")
        self.mag_pb_center_var = tk.StringVar(value=pb_default("pb_center", 0))
        ttk.Combobox(self.body_frame, textvariable=self.mag_pb_center_var, values=pb_all,
                     state="readonly", width=16).grid(row=10, column=1, sticky="w")

        tk.Label(self.body_frame, text="Right PB:").grid(row=11, column=0, sticky="w")
        self.mag_pb_right_var = tk.StringVar(value=pb_default("pb_right", 1))
        ttk.Combobox(self.body_frame, textvariable=self.mag_pb_right_var, values=pb_all,
                     state="readonly", width=16).grid(row=11, column=1, sticky="w")

        tk.Label(self.body_frame, text="Left PB (only 4 options fit -- on-disk format limit):").grid(
            row=12, column=0, sticky="w")
        left_default = pb_default("pb_left", 2)
        if left_default not in pb_left_options:
            left_default = "(none)"
        self.mag_pb_left_var = tk.StringVar(value=left_default)
        ttk.Combobox(self.body_frame, textvariable=self.mag_pb_left_var, values=pb_left_options,
                     state="readonly", width=16).grid(row=12, column=1, sticky="w")

    def _confirm_mag(self):
        s = self.mag_stat_vars
        total = sum(v.get() for v in s.values())
        if total > 200:
            messagebox.showwarning("Mag stats", f"Stats sum to {total}, which exceeds the legit max of 200. Clamping proportionally is not automatic -- please adjust.")

        species_names = [f"{name} ({i})" for i, name in enumerate(db.MAG_SPECIES)]
        species_id = species_names.index(self.mag_species_var.get())

        def resolve_pb(val):
            return None if val == "(none)" else db.PB_NAMES.index(val)

        pb_center = resolve_pb(self.mag_pb_center_var.get())
        pb_right = resolve_pb(self.mag_pb_right_var.get())
        pb_left = resolve_pb(self.mag_pb_left_var.get())

        return items.build_mag(species_id, s["DEF"].get(), s["POW"].get(),
                                s["DEX"].get(), s["MIND"].get(), self.mag_synchro_var.get(),
                                self.mag_iq_var.get(), self.mag_color_var.get(),
                                pb_center, pb_right, pb_left)

    # ---- Tech disk ----
    def _build_tech_disk_body(self):
        existing = self._existing if self._existing and self._existing["kind"] == "tech_disk" else None
        names = [n for n, tid in db.TECHNIQUES]
        default_choice = existing["technique"] if existing and existing["technique"] in names else names[0]

        tk.Label(self.body_frame, text="Technique:").grid(row=0, column=0, sticky="w")
        self.tech_choice = tk.StringVar(value=default_choice)
        ttk.Combobox(self.body_frame, textvariable=self.tech_choice, values=names, state="readonly", width=20).grid(row=0, column=1, sticky="w")

        tk.Label(self.body_frame, text="Level (1-30):").grid(row=1, column=0, sticky="w")
        self.tech_level_var = tk.IntVar(value=existing["level"] if existing else 30)
        tk.Spinbox(self.body_frame, from_=1, to=30, textvariable=self.tech_level_var, width=6).grid(row=1, column=1, sticky="w")

    def _confirm_tech_disk(self):
        names = [n for n, tid in db.TECHNIQUES]
        idx = names.index(self.tech_choice.get())
        _, tech_id = db.TECHNIQUES[idx]
        return items.build_tech_disk(tech_id, self.tech_level_var.get())

    # ---- Part ----
    def _build_part_body(self):
        existing = self._existing if self._existing and self._existing["kind"] == "part" else None
        names = [n for n, d1, d2 in db.PARTS]
        default_choice = names[0]
        if existing:
            match = next((n for n, d1, d2 in db.PARTS
                          if d1 == existing["data1_1"] and d2 == existing["data1_2"]), None)
            if match:
                default_choice = match

        tk.Label(self.body_frame, text="Part item:").grid(row=0, column=0, sticky="w")
        self.part_choice = tk.StringVar(value=default_choice)
        ttk.Combobox(self.body_frame, textvariable=self.part_choice, values=names, state="readonly", width=35).grid(row=0, column=1, sticky="w")

    def _confirm_part(self):
        names = [n for n, d1, d2 in db.PARTS]
        idx = names.index(self.part_choice.get())
        _, d1, d2 = db.PARTS[idx]
        return items.build_part(d1, d2)

    # ---- Tools ----
    def _build_tool_body(self):
        existing = self._existing if self._existing and self._existing["kind"] == "tool_item" else None
        names = [n for n, d1, d2, stackable in db.TOOLS]
        default_choice = names[0]
        if existing:
            match = next((n for n, d1, d2, stackable in db.TOOLS
                          if d1 == existing["tool_kind"] and d2 == existing["tool_variant"]), None)
            if match:
                default_choice = match

        tk.Label(self.body_frame, text="Tool item:").grid(row=0, column=0, sticky="w")
        self.tool_choice = tk.StringVar(value=default_choice)
        combo = ttk.Combobox(self.body_frame, textvariable=self.tool_choice, values=names,
                              state="readonly", width=30)
        combo.grid(row=0, column=1, sticky="w")
        combo.bind("<<ComboboxSelected>>", lambda e: self._update_tool_amount_state())

        tk.Label(self.body_frame, text="Amount (stackable items only):").grid(row=1, column=0, sticky="w")
        default_amount = existing["amount"] if existing and existing.get("stackable") else 1
        self.tool_amount_var = tk.IntVar(value=default_amount)
        self.tool_amount_spin = tk.Spinbox(self.body_frame, from_=1, to=99,
                                            textvariable=self.tool_amount_var, width=6)
        self.tool_amount_spin.grid(row=1, column=1, sticky="w")
        self._update_tool_amount_state()

    def _update_tool_amount_state(self):
        names = [n for n, d1, d2, stackable in db.TOOLS]
        idx = names.index(self.tool_choice.get())
        _, _, _, stackable = db.TOOLS[idx]
        self.tool_amount_spin.config(state="normal" if stackable else "disabled")

    def _confirm_tool(self):
        names = [n for n, d1, d2, stackable in db.TOOLS]
        idx = names.index(self.tool_choice.get())
        _, d1, d2, stackable = db.TOOLS[idx]
        amount = self.tool_amount_var.get() if stackable else 1
        return items.build_tool(d1, d2, amount)

    def _confirm(self):
        cat = self.category_var.get()
        try:
            not_equippable = hasattr(self, "equip_label") and self.equip_label.cget("fg") == "red"
        except tk.TclError:
            not_equippable = False  # stale widget reference -- category has no equip check
        if not_equippable:
            if not messagebox.askyesno(
                "Not equippable",
                self.equip_label.cget("text") + "\n\nAdd it anyway? (it will sit in the "
                "slot but the game will refuse to equip it)"):
                return
        try:
            if cat == "Guns" or cat == "Swords" or cat == "Wands":
                self.result = self._confirm_weapon()
            elif cat == "Armor" or cat == "Shields":
                self.result = self._confirm_armor_shield()
            elif cat == "Units":
                self.result = self._confirm_unit()
            elif cat == "Mags":
                self.result = self._confirm_mag()
            elif cat == "Technique Disks":
                self.result = self._confirm_tech_disk()
            elif cat == "Parts":
                self.result = self._confirm_part()
            elif cat == "Tools":
                self.result = self._confirm_tool()
        except Exception as e:
            messagebox.showerror("Error building item", str(e))
            return
        self.on_confirm(self.result)
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("PSO V2 VMU Editor")
        self.root.geometry("900x780")
        self.root.minsize(850, 700)

        self.file_path = None
        self.image_bytes = None
        self.chain = None
        self.offset = None
        self.data_size = None
        self.serial = None
        self.dec = None  # mutable bytearray of decrypted character payload

        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=8, pady=8)

        # Use a fixed medium-tone color scheme (not system default) so this stays
        # legible in both light and dark mode -- a pale gray background reads as
        # near-invisible in dark mode since tk doesn't auto-adapt.
        self.drop_label = tk.Label(top, text="Drag a VMU .bin file here, or click to open",
                                    relief="ridge", borderwidth=3, height=3,
                                    bg="#2f5d8a", fg="white", font=("", 13, "bold"))
        self.drop_label.pack(fill="x")
        self.drop_label.bind("<Button-1>", lambda e: self._open_file_dialog())

        if _HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self.drop_label.config(text="Drag-and-drop unavailable (tkinterdnd2 not installed) -- click to open")

        self.status_var = tk.StringVar(value="No file loaded.")
        tk.Label(self.root, textvariable=self.status_var, anchor="w", fg="gray").pack(fill="x", padx=8)

        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=8, pady=8)

    def _open_file_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("VMU images", "*.bin"), ("All files", "*.*")])
        if path:
            # Same deferral as _on_drop -- the native open panel's own close
            # animation races with a Tk Toplevel grabbing focus immediately after.
            self.root.after(200, lambda: self._load_path(path))

    def _on_drop(self, event):
        path = event.data.strip("{}")
        # Defer: opening a modal Toplevel synchronously inside the drop callback
        # races against macOS's own drag-session teardown and can leave the new
        # window unable to take real keyboard focus even though it's visible.
        self.root.after(200, lambda: self._load_path(path))

    def _load_path(self, path):
        with open(path, "rb") as f:
            image_bytes = f.read()
        if len(image_bytes) != 131072:
            messagebox.showerror("Not a VMU image", f"Expected a 131072-byte VMU image, got {len(image_bytes)} bytes.")
            return

        entry = vmu.find_character_file(image_bytes)
        if entry is None:
            messagebox.showerror("No character found", "No PSO______SYS file found in this VMU image's directory.")
            return

        config = load_config()
        default_serial = config.get("last_serial")
        error_message = None
        while True:
            dialog = SerialDialog(self.root, error_message, default_serial=default_serial)
            serial = dialog.result_serial
            if serial is None:
                return  # cancelled
            try:
                file_bytes, chain = vmu.read_file_bytes(image_bytes, entry.start_block)
                data_section, data_size, offset = vmu.get_character_data_section(file_bytes)
                dec = bytearray(crypto.decrypt_fixed(data_section, data_size, serial))
                break
            except crypto.ChecksumError as e:
                error_message = str(e)
                default_serial = None  # don't keep re-offering a serial that just failed
                continue

        config["last_serial"] = f"{serial:08X}"
        save_config(config)

        self.file_path = path
        self.image_bytes = image_bytes
        self.chain = chain
        self.offset = offset
        self.data_size = data_size
        self.serial = serial
        self.dec = dec

        self.status_var.set(f"Loaded {os.path.basename(path)} -- character file at blocks {chain[0]}..{chain[-1]}")
        self._build_character_panel()

    def _build_character_panel(self):
        for w in self.main_frame.winfo_children():
            w.destroy()

        # Pack the Save bar at the bottom FIRST so it always gets its natural
        # size reserved. Packing it after a fill="both"/expand=True notebook
        # let the notebook claim all the space whenever the window wasn't
        # tall enough for everything, squeezing this bar down to a sliver
        # with no visible label -- packing bottom-up avoids that entirely.
        save_frame = tk.Frame(self.main_frame)
        save_frame.pack(side="bottom", fill="x", pady=8)
        # A plain ttk.Button (rather than tk.Button with a forced bg/fg) renders
        # with the native macOS Aqua look in both light and dark mode -- forcing
        # colors on a tk.Button produces a flat, oddly-bordered mismatch with the
        # rest of the native UI.
        style = ttk.Style()
        style.configure("Save.TButton", font=("", 12, "bold"), padding=(18, 8))
        ttk.Button(save_frame, text="Save", command=self._save, style="Save.TButton").pack(
            side="right", padx=8)

        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill="both", expand=True)

        char_tab = tk.Frame(notebook)
        notebook.add(char_tab, text="Character")
        self._build_character_tab(char_tab)

        bank_tab = tk.Frame(notebook)
        notebook.add(bank_tab, text=f"Bank ({ch.get_bank_count(self.dec)}/{ch.BANK_CAPACITY})")
        self._build_item_tab(bank_tab, is_bank=True)

        inv_tab = tk.Frame(notebook)
        notebook.add(inv_tab, text=f"Inventory ({ch.get_inventory_count(self.dec)}/{ch.INVENTORY_CAPACITY})")
        self._build_item_tab(inv_tab, is_bank=False)

    def _build_character_tab(self, tab):
        dec = self.dec
        info = tk.LabelFrame(tab, text="Character Info")
        info.pack(fill="x", padx=8, pady=8)

        name = ch.get_name(dec)
        class_name = ch.get_class_name(dec)
        section = ch.get_section_id_name(dec)
        tk.Label(info, text=f"Name: {name}    Class: {class_name}    Section ID: {section}").grid(
            row=0, column=0, columnspan=4, sticky="w", padx=6, pady=4)

        tk.Label(info, text="Level:").grid(row=1, column=0, sticky="w", padx=6)
        self.level_var = tk.IntVar(value=ch.get_displayed_level(dec))
        tk.Spinbox(info, from_=1, to=200, textvariable=self.level_var, width=8).grid(row=1, column=1, sticky="w")

        tk.Label(info, text="EXP:").grid(row=1, column=2, sticky="w", padx=6)
        self.exp_var = tk.IntVar(value=ch.get_exp(dec))
        tk.Entry(info, textvariable=self.exp_var, width=14).grid(row=1, column=3, sticky="w")

        tk.Label(info, text="Meseta:").grid(row=2, column=0, sticky="w", padx=6)
        self.meseta_var = tk.IntVar(value=ch.get_meseta(dec))
        tk.Entry(info, textvariable=self.meseta_var, width=14).grid(row=2, column=1, sticky="w")

        stats = ch.get_stats(dec)
        self.stat_vars = {}
        stat_frame = tk.LabelFrame(tab, text="Stats")
        stat_frame.pack(fill="x", padx=8, pady=8)
        for i, k in enumerate(["ATP", "MST", "EVP", "HP", "DFP", "ATA", "LCK"]):
            tk.Label(stat_frame, text=f"{k}:").grid(row=i // 4, column=(i % 4) * 2, sticky="w", padx=6, pady=2)
            v = tk.IntVar(value=stats[k])
            tk.Entry(stat_frame, textvariable=v, width=8).grid(row=i // 4, column=(i % 4) * 2 + 1, sticky="w")
            self.stat_vars[k] = v

        actions = tk.LabelFrame(tab, text="Actions")
        actions.pack(fill="x", padx=8, pady=8)
        tk.Button(actions, text="Apply level/EXP/meseta/stats above",
                  command=self._apply_character_fields).pack(side="left", padx=6, pady=6)
        tk.Button(actions, text="Sync EXP + stats to Level field (preserve Material bonus)",
                  command=self._sync_to_level).pack(side="left", padx=6, pady=6)
        tk.Button(actions, text=f"Unlock ALL quest flags ({ch.count_quest_flags_set(dec)}/4096 currently set)",
                  command=self._unlock_all_flags).pack(side="left", padx=6, pady=6)

    def _commit_character_fields(self):
        dec = self.dec
        ch.set_displayed_level(dec, self.level_var.get())
        ch.set_exp(dec, self.exp_var.get())
        ch.set_meseta(dec, self.meseta_var.get())
        ch.set_stats(dec, {k: v.get() for k, v in self.stat_vars.items()})

    def _apply_character_fields(self):
        self._commit_character_fields()
        messagebox.showinfo("Applied", "Character fields updated in memory. Click Save to write to disk.")
        self._build_character_panel()

    def _sync_to_level(self):
        target = self.level_var.get()
        final_stats, exp = ch.sync_to_level(self.dec, target, preserve_material_bonus=True)
        messagebox.showinfo("Synced", f"Level {target}: EXP={exp}, stats={final_stats}")
        self._build_character_panel()

    def _unlock_all_flags(self):
        ch.unlock_all_quest_flags(self.dec)
        messagebox.showinfo("Unlocked", "All quest/story flags set across all 4 difficulties.")
        self._build_character_panel()

    def _build_item_tab(self, tab, is_bank):
        capacity = ch.BANK_CAPACITY if is_bank else ch.INVENTORY_CAPACITY
        tree = ttk.Treeview(tab, columns=("desc",), show="tree headings", height=16)
        tree.heading("#0", text="Slot")
        tree.heading("desc", text="Item")
        tree.column("#0", width=60)
        tree.column("desc", width=650)
        tree.pack(fill="both", expand=True, padx=6, pady=6)

        def refresh():
            tree.delete(*tree.get_children())
            count = ch.get_bank_count(self.dec) if is_bank else ch.get_inventory_count(self.dec)
            for slot in range(capacity):
                if is_bank:
                    raw = ch.get_bank_item_raw(self.dec, slot)
                else:
                    raw = ch.get_inventory_item_raw(self.dec, slot)
                is_filled = slot < count
                desc = items.describe_item(raw["data1"], raw["data2"], amount_override=raw.get("amount")) if is_filled else "(empty)"
                tree.insert("", "end", iid=str(slot), text=str(slot), values=(desc,))

        refresh()

        btns = tk.Frame(tab)
        btns.pack(fill="x", padx=6, pady=6)

        def add_item():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("No slot selected", "Select a slot first.")
                return
            slot = int(sel[0])
            count = ch.get_bank_count(self.dec) if is_bank else ch.get_inventory_count(self.dec)
            existing = None
            if slot < count:
                raw = ch.get_bank_item_raw(self.dec, slot) if is_bank else ch.get_inventory_item_raw(self.dec, slot)
                existing = (raw["data1"], raw["data2"])

            def on_confirm(result):
                data1, data2 = result
                item_id = 0x00800000 + slot  # arbitrary unique-ish id
                if is_bank:
                    # Bank slots store their stack count in a wrapper field
                    # outside ItemData -- data1[5] (used by inventory tools)
                    # isn't read by the client for bank storage, so pull the
                    # real amount from the decoded item when it's a stackable
                    # tool instead of leaving the wrapper at its default of 1.
                    decoded = items.decode_item(data1, data2)
                    amount = decoded["amount"] if decoded.get("kind") == "tool_item" and decoded["stackable"] else 1
                    ch.set_bank_item_raw(self.dec, slot, data1, item_id, data2, amount=amount)
                    count = max(ch.get_bank_count(self.dec), slot + 1)
                    ch.set_bank_count(self.dec, count)
                else:
                    ch.set_inventory_item_raw(self.dec, slot, data1, item_id, data2)
                    count = max(ch.get_inventory_count(self.dec), slot + 1)
                    ch.set_inventory_count(self.dec, count)
                refresh()

            AddItemDialog(self.root, on_confirm, existing=existing, char_class_idx=ch.get_class(self.dec))

        def clear_item():
            sel = tree.selection()
            if not sel:
                return
            slot = int(sel[0])
            if is_bank:
                ch.clear_bank_slot(self.dec, slot)
            else:
                ch.clear_inventory_slot(self.dec, slot)
            refresh()

        def clear_all():
            if not messagebox.askyesno("Clear all", f"Clear all {'bank' if is_bank else 'inventory'} items?"):
                return
            if is_bank:
                ch.clear_bank(self.dec)
            else:
                ch.clear_inventory(self.dec)
            refresh()

        tk.Button(btns, text="Add / Edit Item in Selected Slot", command=add_item).pack(side="left", padx=4)
        tk.Button(btns, text="Clear Selected Slot", command=clear_item).pack(side="left", padx=4)
        tk.Button(btns, text=f"Clear All {'Bank' if is_bank else 'Inventory'}", command=clear_all).pack(side="left", padx=4)

    def _save(self):
        if self.dec is None:
            return
        # Commit any pending level/EXP/meseta/stat field edits even if "Apply"
        # was never clicked (e.g. its click didn't register -- same class of
        # macOS/Tk button-click bug worked around in _activate_app above).
        self._commit_character_fields()
        backup_path = self.file_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(self.file_path, backup_path)

        try:
            reenc = crypto.encrypt_fixed(bytes(self.dec), self.data_size, self.serial)
            if not crypto.verify_round_trip(reenc, self.data_size, self.serial, bytes(self.dec)):
                messagebox.showerror("Save failed", "Round-trip verification failed -- NOT writing to disk.")
                return
            vmu.splice_and_save(self.image_bytes, self.chain, self.offset, reenc, self.file_path)
            # Re-read fresh from disk to confirm, matching our validated workflow
            with open(self.file_path, "rb") as f:
                fresh = f.read()
            fresh_file_bytes, _ = vmu.read_file_bytes(fresh, self.chain[0])
            fresh_section, _, _ = vmu.get_character_data_section(fresh_file_bytes)
            crypto.decrypt_fixed(fresh_section, self.data_size, self.serial)  # raises if bad
            self.image_bytes = fresh
            messagebox.showinfo("Saved", f"Saved successfully to {self.file_path}\n(Backup at {backup_path})")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


def main():
    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = App(root)
    _force_to_front(root)
    root.mainloop()


if __name__ == "__main__":
    main()
