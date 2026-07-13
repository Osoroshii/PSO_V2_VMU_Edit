"""PSO VMU Editor -- Android/touch UI.

Four screens: a picker (remembers a VMU folder + serial number, scans that
folder for real characters and shows name/class/level instead of cryptic
filenames), a character editor (level/EXP/meseta/stats/quest-flags, mirroring
the desktop app's Character tab), and Bank/Inventory item editing
(item_screens.py -- ItemListScreen + ItemPickerScreen, mirroring the desktop
app's item tabs and AddItemDialog).

Runs identically on the desktop during development (`python main.py`, from
this directory, with android/venv active) -- Kivy apps are meant to be built
and iterated on like this before ever touching a real device or emulator.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))  # for the psovmu/ symlink

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import storage
import vmu_scan
from psovmu import character as ch
from psovmu import crypto
from session import CharacterSession
from item_screens import ItemListScreen, ItemPickerScreen

try:
    from plyer import filechooser
except ImportError:
    filechooser = None

STAT_KEYS = ["ATP", "MST", "EVP", "HP", "DFP", "ATA", "LCK"]


def _show_message(title, text):
    Popup(title=title, content=Label(text=text), size_hint=(0.85, 0.4)).open()


def _int_field(text=""):
    return TextInput(
        text=str(text), multiline=False, input_filter="int", input_type="number",
    )


class PickerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = storage.load_config()

        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        self.add_widget(root)

        folder_row = BoxLayout(size_hint=(1, None), height=44, spacing=8)
        self.folder_label = Label(
            text=self._folder_display(), halign="left", valign="middle", shorten=True
        )
        self.folder_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        pick_btn = Button(text="Choose VMU Folder", size_hint=(None, 1), width=200)
        pick_btn.bind(on_release=lambda *_: self._pick_folder())
        folder_row.add_widget(self.folder_label)
        folder_row.add_widget(pick_btn)
        root.add_widget(folder_row)

        serial_row = BoxLayout(size_hint=(1, None), height=44, spacing=8)
        serial_row.add_widget(Label(text="Serial:", size_hint=(None, 1), width=60))
        self.serial_input = TextInput(
            text=self.config.get("serial", ""), multiline=False, hint_text="e.g. 4E62F237"
        )
        save_serial_btn = Button(text="Save + Rescan", size_hint=(None, 1), width=150)
        save_serial_btn.bind(on_release=lambda *_: self._save_serial_and_rescan())
        serial_row.add_widget(self.serial_input)
        serial_row.add_widget(save_serial_btn)
        root.add_widget(serial_row)

        self.status_label = Label(text="", size_hint=(1, None), height=24)
        root.add_widget(self.status_label)

        self.results_box = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=6)
        self.results_box.bind(minimum_height=self.results_box.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.results_box)
        root.add_widget(scroll)

    def on_pre_enter(self, *args):
        if self.config.get("folder") and self.config.get("serial"):
            self.rescan()

    def _folder_display(self):
        folder = self.config.get("folder")
        return f"Folder: {folder}" if folder else "No folder chosen yet"

    def _pick_folder(self):
        if filechooser is None:
            _show_message("Unavailable", "plyer's filechooser isn't installed.")
            return
        try:
            filechooser.choose_dir(on_selection=self._on_folder_chosen)
        except Exception as e:  # plyer's Android backend can raise NotImplementedError etc.
            _show_message("Folder picker failed", str(e))

    def _on_folder_chosen(self, selection):
        if not selection:
            return
        self.config["folder"] = selection[0]
        storage.save_config(self.config)
        self.folder_label.text = self._folder_display()
        self.rescan()

    def _save_serial_and_rescan(self):
        serial_text = self.serial_input.text.strip()
        if not serial_text:
            _show_message("No serial", "Enter your disc/account serial number first.")
            return
        try:
            int(serial_text, 16)
        except ValueError:
            _show_message("Invalid serial", "Serial must be hex, e.g. 4E62F237.")
            return
        self.config["serial"] = serial_text
        storage.save_config(self.config)
        self.rescan()

    def rescan(self):
        self.results_box.clear_widgets()
        folder = self.config.get("folder")
        serial_text = self.config.get("serial")
        if not folder:
            self.status_label.text = "Choose a folder to scan for VMU files."
            return
        if not serial_text:
            self.status_label.text = "Enter a serial number to decrypt character names."
            return
        serial = int(serial_text, 16)
        results = vmu_scan.scan_folder(folder, serial)
        if not results:
            self.status_label.text = "No .bin files found in that folder."
            return
        self.status_label.text = f"{sum(r.ok for r in results)} character(s) found of {len(results)} file(s)."
        for r in results:
            text = r.label if r.ok else f"\U0001F512 {r.label} -- {r.error}"
            row = Button(text=text, size_hint=(1, None), height=48, halign="left")
            row.bind(size=lambda w, s: setattr(w, "text_size", s))
            if r.ok:
                row.bind(on_release=lambda _btn, path=r.path: self._open_character(path, serial))
            else:
                row.disabled = True
            self.results_box.add_widget(row)

    def _open_character(self, path, serial):
        try:
            session = CharacterSession.load(path, serial)
        except crypto.ChecksumError as e:
            _show_message("Can't open", str(e))
            return
        except Exception as e:
            _show_message("Can't open", f"Not a readable character file ({e}).")
            return
        editor = self.manager.get_screen("editor")
        editor.load_session(session)
        self.manager.current = "editor"


class EditorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = None
        self.stat_inputs = {}

        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        self.add_widget(root)

        top_row = BoxLayout(size_hint=(1, None), height=40, spacing=8)
        back_btn = Button(text="< Back", size_hint=(None, 1), width=90)
        back_btn.bind(on_release=lambda *_: self._go_back())
        top_row.add_widget(back_btn)
        self.title_label = Label(text="", halign="left", valign="middle")
        self.title_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        top_row.add_widget(self.title_label)
        root.add_widget(top_row)

        fields = GridLayout(cols=4, size_hint=(1, None), height=44)
        fields.add_widget(Label(text="Level:", size_hint=(None, 1), width=70))
        self.level_input = _int_field()
        fields.add_widget(self.level_input)
        fields.add_widget(Label(text="EXP:", size_hint=(None, 1), width=70))
        self.exp_input = _int_field()
        fields.add_widget(self.exp_input)
        root.add_widget(fields)

        meseta_row = GridLayout(cols=4, size_hint=(1, None), height=44)
        meseta_row.add_widget(Label(text="Meseta:", size_hint=(None, 1), width=70))
        self.meseta_input = _int_field()
        meseta_row.add_widget(self.meseta_input)
        meseta_row.add_widget(Label())
        meseta_row.add_widget(Label())
        root.add_widget(meseta_row)

        stat_grid = GridLayout(cols=4, size_hint=(1, None), height=44 * 2, spacing=6)
        for k in STAT_KEYS:
            stat_grid.add_widget(Label(text=f"{k}:", size_hint=(None, 1), width=50))
            field = _int_field()
            self.stat_inputs[k] = field
            stat_grid.add_widget(field)
        root.add_widget(stat_grid)

        actions = BoxLayout(size_hint=(1, None), height=48, spacing=8)
        apply_btn = Button(text="Apply fields")
        apply_btn.bind(on_release=lambda *_: self._apply_fields())
        sync_btn = Button(text="Sync to Level")
        sync_btn.bind(on_release=lambda *_: self._sync_to_level())
        unlock_btn = Button(text="Unlock ALL quest flags")
        unlock_btn.bind(on_release=lambda *_: self._unlock_flags())
        actions.add_widget(apply_btn)
        actions.add_widget(sync_btn)
        actions.add_widget(unlock_btn)
        root.add_widget(actions)

        self.status_label = Label(text="", size_hint=(1, None), height=48)
        root.add_widget(self.status_label)

        item_row = BoxLayout(size_hint=(1, None), height=52, spacing=8)
        self.bank_btn = Button(text="Bank")
        self.bank_btn.bind(on_release=lambda *_: self._open_items(is_bank=True))
        self.inventory_btn = Button(text="Inventory")
        self.inventory_btn.bind(on_release=lambda *_: self._open_items(is_bank=False))
        item_row.add_widget(self.bank_btn)
        item_row.add_widget(self.inventory_btn)
        root.add_widget(item_row)

        save_btn = Button(text="Save", size_hint=(1, None), height=56, bold=True)
        save_btn.bind(on_release=lambda *_: self._save())
        root.add_widget(save_btn)

        root.add_widget(BoxLayout())  # spacer so short content doesn't stretch oddly

    def on_pre_enter(self, *args):
        if self.session is not None:
            self._update_item_buttons()  # reflect any items added/cleared since last shown

    def load_session(self, session):
        self.session = session
        dec = session.dec
        name = ch.get_name(dec).strip() or "(unnamed)"
        self.title_label.text = (
            f"{name}  --  {ch.get_class_name(dec)}, {ch.get_section_id_name(dec)}"
        )
        self.level_input.text = str(ch.get_displayed_level(dec))
        self.exp_input.text = str(ch.get_exp(dec))
        self.meseta_input.text = str(ch.get_meseta(dec))
        stats = ch.get_stats(dec)
        for k in STAT_KEYS:
            self.stat_inputs[k].text = str(stats[k])
        self._update_status()
        self._update_item_buttons()

    def _update_item_buttons(self):
        dec = self.session.dec
        self.bank_btn.text = f"Bank ({ch.get_bank_count(dec)}/{ch.BANK_CAPACITY})"
        self.inventory_btn.text = f"Inventory ({ch.get_inventory_count(dec)}/{ch.INVENTORY_CAPACITY})"

    def _open_items(self, is_bank):
        item_screen = self.manager.get_screen("items")
        item_screen.open_for(self.session, is_bank)
        self.manager.current = "items"

    def _update_status(self):
        if self.session is None:
            return
        n = ch.count_quest_flags_set(self.session.dec)
        self.status_label.text = f"Quest flags set: {n}/4096"

    def _field_int(self, widget, fallback=0):
        try:
            return int(widget.text)
        except (TypeError, ValueError):
            return fallback

    def _commit_fields(self):
        dec = self.session.dec
        ch.set_displayed_level(dec, self._field_int(self.level_input, ch.get_displayed_level(dec)))
        ch.set_exp(dec, self._field_int(self.exp_input, ch.get_exp(dec)))
        ch.set_meseta(dec, self._field_int(self.meseta_input, ch.get_meseta(dec)))
        current = ch.get_stats(dec)
        ch.set_stats(dec, {k: self._field_int(self.stat_inputs[k], current[k]) for k in STAT_KEYS})

    def _apply_fields(self):
        self._commit_fields()
        _show_message("Applied", "Character fields updated in memory. Tap Save to write to disk.")
        self._update_status()

    def _sync_to_level(self):
        target = self._field_int(self.level_input, ch.get_displayed_level(self.session.dec))
        final_stats, exp = ch.sync_to_level(self.session.dec, target, preserve_material_bonus=True)
        self.exp_input.text = str(exp)
        for k in STAT_KEYS:
            if k in final_stats:
                self.stat_inputs[k].text = str(final_stats[k])
        _show_message("Synced", f"Level {target}: EXP={exp}")

    def _unlock_flags(self):
        ch.unlock_all_quest_flags(self.session.dec)
        self._update_status()
        _show_message("Unlocked", "All quest/story flags set across all 4 difficulties.")

    def _save(self):
        if self.session is None:
            return
        self._commit_fields()
        try:
            self.session.save()
        except Exception as e:
            _show_message("Save failed", str(e))
            return
        _show_message("Saved", f"Saved successfully.\n(Backup at {self.session.path}.bak)")

    def _go_back(self):
        self.manager.current = "picker"
        picker = self.manager.get_screen("picker")
        picker.rescan()  # reflect any level/name changes just saved


class PSOVMUApp(App):
    def build(self):
        self.title = "PSO VMU Editor"
        sm = ScreenManager()
        sm.add_widget(PickerScreen(name="picker"))
        sm.add_widget(EditorScreen(name="editor"))
        sm.add_widget(ItemListScreen(name="items"))
        sm.add_widget(ItemPickerScreen(name="item_picker"))
        sm.current = "picker"
        return sm


if __name__ == "__main__":
    PSOVMUApp().run()
