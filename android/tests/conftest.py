import os
import subprocess
import sys

# Make android/ itself importable (session.py, vmu_scan.py, storage.py,
# fileio.py, and the psovmu/ symlink all live there as top-level modules,
# not a package) -- same pattern the root tests/ suite uses for the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def _detect_kivy_window_support():
    """Constructing any real Kivy widget lazily calls EventLoop.ensure_window(),
    which calls sys.exit(1) -- not a catchable Exception -- if no window
    provider can attach to a display. Confirmed on GitHub's macOS-hosted CI
    runners specifically: unlike Ubuntu (fixable with xvfb-run) and a real
    developer Mac (has a logged-in GUI session), those runners have no
    display at all, and Kivy's SDL2 backend has no headless fallback.

    Catching that sys.exit in-process is NOT safe to do inside a fixture --
    tried it, and it also corrupted pytest's own fixture-teardown bookkeeping
    (a stale FixtureDef._finalizers list), turning one real failure into a
    cascade of unrelated-looking errors on every later test sharing this
    fixture. Running the probe in a subprocess isolates that sys.exit(1) to a
    throwaway process, so pytest never sees it -- just an exit code."""
    result = subprocess.run(
        [sys.executable, "-c", "from kivy.uix.widget import Widget; Widget()"],
        capture_output=True,
    )
    return result.returncode == 0


_KIVY_WINDOW_AVAILABLE = _detect_kivy_window_support()


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
    if not _KIVY_WINDOW_AVAILABLE:
        pytest.skip("No display available for Kivy to create a Window (needed to construct real widgets)")

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
