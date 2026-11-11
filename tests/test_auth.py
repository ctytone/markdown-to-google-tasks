"""Unit tests for OAuth and Google service construction."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError

import auth


def test_authenticate_reuses_valid_cached_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load valid cached credentials without refreshing or opening OAuth."""
    token_file = tmp_path / "token.json"
    token_file.write_text("cached", encoding="utf-8")
    credentials = MagicMock(valid=True)
    load_credentials = MagicMock(return_value=credentials)
    oauth_flow = MagicMock()
    monkeypatch.setattr(auth, "TOKEN_FILE", token_file)
    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_file",
        load_credentials,
    )
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        oauth_flow,
    )

    result = auth.authenticate()

    assert result is credentials
    load_credentials.assert_called_once_with(
        str(token_file),
        auth.SCOPES,
    )
    credentials.refresh.assert_not_called()
    oauth_flow.assert_not_called()
    assert token_file.read_text(encoding="utf-8") == "cached"


def test_authenticate_refreshes_and_rewrites_expired_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refresh expired cached credentials and persist their new token."""
    token_file = tmp_path / "token.json"
    token_file.write_text("expired", encoding="utf-8")
    credentials = MagicMock(
        valid=False,
        expired=True,
        refresh_token="refresh-token",
    )
    credentials.to_json.return_value = '{"token": "refreshed"}'
    request = MagicMock(name="request")
    monkeypatch.setattr(auth, "TOKEN_FILE", token_file)
    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_file",
        MagicMock(return_value=credentials),
    )
    monkeypatch.setattr(auth, "Request", MagicMock(return_value=request))

    result = auth.authenticate()

    assert result is credentials
    credentials.refresh.assert_called_once_with(request)
    assert token_file.read_text(encoding="utf-8") == '{"token": "refreshed"}'


def test_authenticate_runs_desktop_oauth_when_token_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the desktop OAuth flow and create token.json when needed."""
    token_file = tmp_path / "token.json"
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}", encoding="utf-8")
    credentials = MagicMock(valid=True)
    credentials.to_json.return_value = '{"token": "new"}'
    flow = MagicMock()
    flow.run_local_server.return_value = credentials
    create_flow = MagicMock(return_value=flow)
    monkeypatch.setattr(auth, "TOKEN_FILE", token_file)
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", credentials_file)
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        create_flow,
    )

    result = auth.authenticate()

    assert result is credentials
    create_flow.assert_called_once_with(
        str(credentials_file),
        auth.SCOPES,
    )
    flow.run_local_server.assert_called_once_with(port=0)
    assert token_file.read_text(encoding="utf-8") == '{"token": "new"}'


def test_authenticate_reauthorizes_when_refresh_token_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replace a revoked cached token through the desktop OAuth flow."""
    token_file = tmp_path / "token.json"
    token_file.write_text("revoked", encoding="utf-8")
    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text("{}", encoding="utf-8")
    revoked_credentials = MagicMock(
        valid=False,
        expired=True,
        refresh_token="revoked-refresh-token",
    )
    revoked_credentials.refresh.side_effect = RefreshError(
        "Token has been expired or revoked."
    )
    new_credentials = MagicMock(valid=True)
    new_credentials.to_json.return_value = '{"token": "reauthorized"}'
    flow = MagicMock()
    flow.run_local_server.return_value = new_credentials
    create_flow = MagicMock(return_value=flow)
    request = MagicMock(name="request")
    monkeypatch.setattr(auth, "TOKEN_FILE", token_file)
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", credentials_file)
    monkeypatch.setattr(auth, "Request", MagicMock(return_value=request))
    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_file",
        MagicMock(return_value=revoked_credentials),
    )
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        create_flow,
    )

    result = auth.authenticate()

    assert result is new_credentials
    revoked_credentials.refresh.assert_called_once_with(request)
    create_flow.assert_called_once_with(
        str(credentials_file),
        auth.SCOPES,
    )
    flow.run_local_server.assert_called_once_with(port=0)
    assert token_file.read_text(encoding="utf-8") == (
        '{"token": "reauthorized"}'
    )


def test_get_service_builds_tasks_v1_with_authenticated_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construct the expected Google Tasks discovery service."""
    credentials = MagicMock(name="credentials")
    service = MagicMock(name="tasks_service")
    build = MagicMock(return_value=service)
    monkeypatch.setattr(
        auth,
        "authenticate",
        MagicMock(return_value=credentials),
    )
    monkeypatch.setattr(auth, "build", build)

    assert auth.get_service() is service
    build.assert_called_once_with(
        "tasks",
        "v1",
        credentials=credentials,
    )


def test_authenticate_explains_missing_credentials_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Point the user at the expected folder when credentials are absent."""
    monkeypatch.setattr(auth, "TOKEN_FILE", tmp_path / "token.json")
    monkeypatch.setattr(auth, "CREDENTIALS_FILE", tmp_path / "credentials.json")

    with pytest.raises(FileNotFoundError, match="credentials.json"):
        auth.authenticate()
