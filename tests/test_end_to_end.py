"""Pytest-native end-to-end tests for the complete importer pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

import import_project
from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    CreateTaskListOperation,
    build_execution_plan,
)
from markdown_parser import MarkdownFormatError, parse_markdown
from models import Project, Section
from tasks_api import parent_task_exists, subtask_exists


def test_valid_markdown_builds_ordered_model_and_plan(
    project_file: Path,
) -> None:
    """Exercise file parsing, domain modeling, and planning together."""
    project = parse_markdown(project_file)
    plan = build_execution_plan(project)

    assert isinstance(project, Project)
    assert project == Project(
        project_name="Test Project",
        sections=[
            Section(
                title="Planning",
                tasks=["Create folder", "Review plan"],
            ),
            Section(title="Development", tasks=["Write code"]),
        ],
    )
    assert plan.operations == (
        CreateTaskListOperation("Test Project"),
        CreateParentTaskOperation("Planning"),
        CreateSubtaskOperation("Create folder", "Planning"),
        CreateSubtaskOperation("Review plan", "Planning"),
        CreateParentTaskOperation("Development"),
        CreateSubtaskOperation("Write code", "Development"),
    )


@pytest.mark.parametrize(
    ("content", "expected_message"),
    [
        ("", "level-one project heading"),
        ("## Section\n- Task", "section appears before"),
        ("# Project\n- Task", "task appears before"),
        ("# Project\nparagraph", "unsupported Markdown"),
    ],
)
def test_malformed_or_empty_markdown_is_rejected(
    tmp_path: Path,
    content: str,
    expected_message: str,
) -> None:
    """Reject empty and malformed temporary project files."""
    path = tmp_path / "invalid.md"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(MarkdownFormatError, match=expected_message):
        parse_markdown(path)


def test_dry_run_never_accesses_google(
    project_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Prove that dry-run mode performs no authentication or API calls."""
    get_service = MagicMock(name="get_service")
    monkeypatch.setattr(import_project, "get_service", get_service)
    user_input = MagicMock(name="input")
    monkeypatch.setattr("builtins.input", user_input)

    status = import_project.main([str(project_file), "--dry-run"])

    assert status == 0
    user_input.assert_not_called()
    get_service.assert_not_called()
    assert "Nothing has been created." in capsys.readouterr().out


def test_execute_runs_every_operation_in_source_order(
    project_file: Path,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Execute the full pipeline using only a mocked Google service."""
    monkeypatch.setattr(
        import_project,
        "get_service",
        MagicMock(return_value=google_service),
    )

    status = import_project.main(
        [str(project_file), "--execute", "--force"]
    )

    assert status == 0
    google_service.tasklists.return_value.insert.assert_called_once_with(
        body={"title": "Test Project"}
    )
    assert google_service.tasks.return_value.insert.call_args_list == [
        call(tasklist="list-id", body={"title": "Planning"}),
        call(
            tasklist="list-id",
            body={"title": "Create folder"},
            parent="planning-id",
        ),
        call(
            tasklist="list-id",
            body={"title": "Review plan"},
            parent="planning-id",
        ),
        call(tasklist="list-id", body={"title": "Development"}),
        call(
            tasklist="list-id",
            body={"title": "Write code"},
            parent="development-id",
        ),
    ]
    assert "Completed Successfully" in capsys.readouterr().out


def test_duplicate_task_list_prevents_all_create_calls(
    project_file: Path,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent execution when the destination task list already exists."""
    google_service.tasklists.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "existing", "title": " test project "}]
    }
    monkeypatch.setattr(
        import_project,
        "get_service",
        MagicMock(return_value=google_service),
    )

    status = import_project.main(
        [str(project_file), "--execute", "--force"]
    )

    assert status == 0
    google_service.tasklists.return_value.insert.assert_not_called()
    google_service.tasks.return_value.insert.assert_not_called()


def test_parent_and_subtask_duplicate_helpers_are_parent_scoped(
    google_service: MagicMock,
) -> None:
    """Verify parent and subtask duplicate matching without writes."""
    google_service.tasks.return_value.list.return_value.execute.side_effect = [
        {"items": [{"id": "parent-id", "title": " Planning "}]},
        {
            "items": [
                {
                    "id": "child-id",
                    "title": "Create folder",
                    "parent": "parent-id",
                }
            ]
        },
        {
            "items": [
                {
                    "id": "child-id",
                    "title": "Create folder",
                    "parent": "parent-id",
                }
            ]
        },
    ]

    assert parent_task_exists(google_service, "list-id", "planning")
    assert subtask_exists(
        google_service,
        "list-id",
        "parent-id",
        "create folder",
    )
    assert not subtask_exists(
        google_service,
        "list-id",
        "different-parent",
        "create folder",
    )


def test_command_line_requires_exactly_one_mode() -> None:
    """Require one mutually exclusive execution-mode argument."""
    with pytest.raises(SystemExit) as missing_mode:
        import_project._parse_arguments(["project.md"])
    assert missing_mode.value.code == 2

    with pytest.raises(SystemExit) as conflicting_modes:
        import_project._parse_arguments(
            ["project.md", "--dry-run", "--execute"]
        )
    assert conflicting_modes.value.code == 2
