"""PSO VMU Editor -- Android/touch UI.

First screen only, for now: remember a VMU folder + serial number once, then
scan that folder every time the app opens and show which .bin files have a
real character in them (by name/class/level) so the user can pick one without
having to remember cryptic filenames like vmu_save_C2.bin.

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
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

import storage
import vmu_scan

try:
    from plyer import filechooser
except ImportError:
    filechooser = None


def _show_message(title, text):
    Popup(title=title, content=Label(text=text), size_hint=(0.85, 0.4)).open()


class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=12, spacing=10, **kwargs)
        self.config = storage.load_config()

        folder_row = BoxLayout(size_hint=(1, None), height=44, spacing=8)
        self.folder_label = Label(
            text=self._folder_display(), halign="left", valign="middle", shorten=True
        )
        self.folder_label.bind(size=lambda w, s: setattr(w, "text_size", s))
        pick_btn = Button(text="Choose VMU Folder", size_hint=(None, 1), width=200)
        pick_btn.bind(on_release=lambda *_: self._pick_folder())
        folder_row.add_widget(self.folder_label)
        folder_row.add_widget(pick_btn)
        self.add_widget(folder_row)

        serial_row = BoxLayout(size_hint=(1, None), height=44, spacing=8)
        serial_row.add_widget(Label(text="Serial:", size_hint=(None, 1), width=60))
        self.serial_input = TextInput(
            text=self.config.get("serial", ""), multiline=False, hint_text="e.g. 4E62F237"
        )
        save_serial_btn = Button(text="Save + Rescan", size_hint=(None, 1), width=150)
        save_serial_btn.bind(on_release=lambda *_: self._save_serial_and_rescan())
        serial_row.add_widget(self.serial_input)
        serial_row.add_widget(save_serial_btn)
        self.add_widget(serial_row)

        self.status_label = Label(text="", size_hint=(1, None), height=24)
        self.add_widget(self.status_label)

        self.results_box = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=6)
        self.results_box.bind(minimum_height=self.results_box.setter("height"))
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.results_box)
        self.add_widget(scroll)

        if self.config.get("folder") and self.config.get("serial"):
            self._rescan()

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
        self._rescan()

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
        self._rescan()

    def _rescan(self):
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
                row.bind(on_release=lambda _btn, path=r.path: self._open_character(path))
            else:
                row.disabled = True
            self.results_box.add_widget(row)

    def _open_character(self, path):
        # Character editor screen comes next -- for now just confirm which file
        # would be opened, so the picker flow itself is fully testable already.
        _show_message("Selected", path)


class PSOVMUApp(App):
    def build(self):
        self.title = "PSO VMU Editor"
        return RootWidget()


if __name__ == "__main__":
    PSOVMUApp().run()
