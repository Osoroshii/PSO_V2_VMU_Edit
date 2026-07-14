import os
import sys

# Make android/ itself importable (session.py, vmu_scan.py, storage.py,
# fileio.py, and the psovmu/ symlink all live there as top-level modules,
# not a package) -- same pattern the root tests/ suite uses for the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class _FakeApp:
    """Stand-in for App.get_running_app() -- constructing any real screen
    below pulls in storage.py, which otherwise falls back to the process cwd
    for its config file (see storage.py's docstring) when no App is running.
    Without this, importing/instantiating screens in a test would read/write
    a stray psovmu_android_config.json in whatever directory pytest happens
    to run from."""

    def __init__(self, data_dir):
        self.user_data_dir = str(data_dir)


@pytest.fixture
def app_screen_manager(tmp_path, monkeypatch):
    """A ScreenManager with one fresh instance of each real screen the app
    uses, wired up exactly like PSOVMUApp.build() in main.py -- so screens
    that call self.manager.get_screen(...)/self.manager.current = ... behave
    the same as they do in the running app."""
    import storage
    monkeypatch.setattr(storage.App, "get_running_app", staticmethod(lambda: _FakeApp(tmp_path / "appdata")))

    from kivy.uix.screenmanager import ScreenManager

    import main as main_mod
    import item_screens as item_screens_mod

    sm = ScreenManager()
    for screen in (
        main_mod.PickerScreen(name="picker"),
        main_mod.EditorScreen(name="editor"),
        item_screens_mod.ItemListScreen(name="items"),
        item_screens_mod.ItemPickerScreen(name="item_picker"),
    ):
        sm.add_widget(screen)
    return sm
