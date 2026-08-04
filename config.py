"""Configuration for the Google Tasks importer."""

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/tasks"]

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
