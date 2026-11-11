"""Shared pytest fixtures and account-safety guards."""

from collections.abc import Iterator
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

import pytest

import auth
import gui
import import_project


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Provide an isolated path without pytest's shared numbered temp root."""
    with tempfile.TemporaryDirectory(prefix="google-tasks-tests-") as directory:
        yield Path(directory)


@pytest.fixture(autouse=True)
def prevent_real_google_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail any test that reaches authentication without an explicit mock."""

    def forbidden_authentication(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "Automated tests must not authenticate with a real Google account."
        )

    monkeypatch.setattr(
        import_project,
        "get_service",
        forbidden_authentication,
    )
    monkeypatch.setattr(gui, "get_service", forbidden_authentication)
    monkeypatch.setattr(auth, "Request", forbidden_authentication)
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        forbidden_authentication,
    )
    monkeypatch.setattr(auth, "build", forbidden_authentication)


@pytest.fixture
def markdown_text() -> str:
    """Return a representative ordered Markdown project."""
    return """# Test Project

## Planning
- Create folder
- Review plan

## Development
- Write code
"""


@pytest.fixture
def project_file(tmp_path: Path, markdown_text: str) -> Path:
    """Create a temporary Markdown project file."""
    path = tmp_path / "project.md"
    path.write_text(markdown_text, encoding="utf-8")
    return path


@pytest.fixture
def google_service() -> MagicMock:
    """Return a fully mocked Google Tasks service for one test project."""
    service = MagicMock(name="google_tasks_service")
    service.tasklists.return_value.list.return_value.execute.return_value = {
        "items": []
    }
    service.tasklists.return_value.insert.return_value.execute.return_value = {
        "id": "list-id",
        "title": "Test Project",
    }
    service.tasks.return_value.list.return_value.execute.return_value = {
        "items": []
    }
    service.tasks.return_value.insert.return_value.execute.side_effect = [
        {"id": "planning-id", "title": "Planning"},
        {
            "id": "create-folder-id",
            "title": "Create folder",
            "parent": "planning-id",
        },
        {
            "id": "review-plan-id",
            "title": "Review plan",
            "parent": "planning-id",
        },
        {"id": "development-id", "title": "Development"},
        {
            "id": "write-code-id",
            "title": "Write code",
            "parent": "development-id",
        },
    ]
    return service
