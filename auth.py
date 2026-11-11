"""Google OAuth authentication and Tasks service creation."""

from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import CREDENTIALS_FILE, SCOPES, TOKEN_FILE


def authenticate() -> Credentials:
    """Load, refresh, or create Google OAuth credentials."""
    credentials = None

    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if not credentials or not credentials.valid:
        needs_authorization = True
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                needs_authorization = False
            except RefreshError:
                credentials = None

        if needs_authorization:
            if not CREDENTIALS_FILE.is_file():
                raise FileNotFoundError(
                    "Google OAuth client file not found. Place "
                    f"credentials.json in: {CREDENTIALS_FILE.parent}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            credentials = flow.run_local_server(port=0)

        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def get_service() -> Any:
    """Authenticate and return a Google Tasks API service."""
    return build("tasks", "v1", credentials=authenticate())
