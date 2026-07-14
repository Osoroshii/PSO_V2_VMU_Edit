"""Tests for storage.py's config persistence. storage.App.get_running_app()
is monkeypatched directly rather than spinning up a real Kivy App -- these
tests only care about the module's own file-handling logic, not Kivy's App
lifecycle."""
import json

import storage


class _FakeApp:
    def __init__(self, data_dir):
        self.user_data_dir = str(data_dir)


def _use_fake_app(monkeypatch, data_dir):
    monkeypatch.setattr(storage.App, "get_running_app", staticmethod(lambda: _FakeApp(data_dir)))


def test_load_config_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    _use_fake_app(monkeypatch, tmp_path / "appdata")
    assert storage.load_config() == {}


def test_save_then_load_config_round_trip(tmp_path, monkeypatch):
    _use_fake_app(monkeypatch, tmp_path / "appdata")
    config = {"folder": "/some/vmu/folder", "serial": "4E62F237"}

    storage.save_config(config)

    assert storage.load_config() == config


def test_config_path_creates_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "appdata" / "nested"
    _use_fake_app(monkeypatch, data_dir)

    storage.save_config({"a": 1})

    assert data_dir.is_dir()
    assert (data_dir / "psovmu_android_config.json").exists()


def test_load_config_invalid_json_returns_empty_dict(tmp_path, monkeypatch):
    data_dir = tmp_path / "appdata"
    _use_fake_app(monkeypatch, data_dir)
    data_dir.mkdir()
    (data_dir / "psovmu_android_config.json").write_text("not valid json{")

    assert storage.load_config() == {}


def test_config_path_falls_back_to_cwd_when_no_running_app(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.App, "get_running_app", staticmethod(lambda: None))
    monkeypatch.chdir(tmp_path)

    storage.save_config({"folder": "x"})

    assert (tmp_path / "psovmu_android_config.json").exists()
    with open(tmp_path / "psovmu_android_config.json") as f:
        assert json.load(f) == {"folder": "x"}
