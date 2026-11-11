"""Configuration for the Google Tasks importer.

The OAuth token is stored in a per-user application folder so it survives
between runs of the packaged executable (a one-file PyInstaller build unpacks
into a temporary directory that is deleted on exit).
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

APP_NAME = "Google Tasks Importer"

SCOPES = ["https://www.googleapis.com/auth/tasks"]

BASE_DIR = Path(__file__).resolve().parent


def _app_data_dir() -> Path:
    """Return the per-user folder that holds the token and credentials."""
    root = os.environ.get("APPDATA")
    return (Path(root) if root else Path.home()) / APP_NAME


def _program_dir() -> Path:
    """Return the folder containing the executable or source files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return BASE_DIR


def _credential_candidates() -> list[Path]:
    """Return credential locations in lookup order."""
    candidates = [APP_DATA_DIR / "credentials.json"]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "credentials.json")
    candidates.append(_program_dir() / "credentials.json")
    return candidates


def _find_credentials_file() -> Path:
    """Return the first existing credentials file, else the preferred path."""
    candidates = _credential_candidates()
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


APP_DATA_DIR = _app_data_dir()
TOKEN_FILE = APP_DATA_DIR / "token.json"
CREDENTIALS_FILE = _find_credentials_file()
