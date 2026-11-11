"""Tests for token and credential file locations."""

from pathlib import Path
import sys

import pytest

import config


def test_token_is_stored_in_app_data_folder() -> None:
    assert config.TOKEN_FILE.parent == config.APP_DATA_DIR
    assert config.APP_DATA_DIR.name == config.APP_NAME


def test_app_data_dir_uses_appdata_or_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert config._app_data_dir() == tmp_path / config.APP_NAME

    monkeypatch.delenv("APPDATA")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path / "home")
    assert config._app_data_dir() == tmp_path / "home" / config.APP_NAME


def test_credentials_lookup_prefers_app_data_then_bundle_then_program(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_data = tmp_path / "appdata"
    bundle = tmp_path / "bundle"
    program = tmp_path / "program"
    for folder in (app_data, bundle, program):
        folder.mkdir()
    monkeypatch.setattr(config, "APP_DATA_DIR", app_data)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(program / "app.exe"))

    # Nothing exists yet: point the user at the app-data folder.
    assert config._find_credentials_file() == app_data / "credentials.json"

    (program / "credentials.json").write_text("{}", encoding="utf-8")
    assert config._find_credentials_file() == program / "credentials.json"

    (bundle / "credentials.json").write_text("{}", encoding="utf-8")
    assert config._find_credentials_file() == bundle / "credentials.json"

    (app_data / "credentials.json").write_text("{}", encoding="utf-8")
    assert config._find_credentials_file() == app_data / "credentials.json"


def test_program_dir_is_source_folder_when_not_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert config._program_dir() == config.BASE_DIR
