"""Persisted app settings (VMU folder path + last-used serial), stored under
Kivy's App.user_data_dir -- this resolves to the right place automatically on
every platform Kivy supports (a dotfile under $HOME in desktop dev, the app's
private internal storage on a packaged Android APK), so this module doesn't
need any platform-specific branching itself.
"""
import json
import os

from kivy.app import App

_CONFIG_FILENAME = "psovmu_android_config.json"


def _config_path():
    app = App.get_running_app()
    data_dir = app.user_data_dir if app else "."
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, _CONFIG_FILENAME)


def load_config():
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(config):
    try:
        with open(_config_path(), "w") as f:
            json.dump(config, f)
    except OSError:
        pass  # best-effort -- losing a remembered setting isn't worth crashing over
