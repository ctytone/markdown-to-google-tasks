"""Tests for the GUI's non-visual helpers and import worker."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from execution_plan import build_execution_plan
import gui
from markdown_parser import parse_markdown_text


def test_plan_rows_follow_operation_order(project_file: Path) -> None:
    plan = gui.load_plan(project_file)

    assert gui.plan_rows(plan) == [
        ("list", "Test Project"),
        ("parent", "Planning"),
        ("subtask", "Create folder"),
        ("subtask", "Review plan"),
        ("parent", "Development"),
        ("subtask", "Write code"),
    ]
    assert len(gui.plan_rows(plan)) == len(plan)


def test_plan_summary_pluralizes(project_file: Path) -> None:
    assert gui.plan_summary(gui.load_plan(project_file)) == "2 tasks, 3 subtasks"
    single = build_execution_plan(
        parse_markdown_text("# One\n## Only\n- Item\n")
    )
    assert gui.plan_summary(single) == "1 task, 1 subtask"


def test_run_import_reports_progress_and_result(
    project_file: Path,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gui, "get_service", MagicMock(return_value=google_service))
    events: list[tuple] = []

    gui.run_import(gui.load_plan(project_file), events.append)

    progress = [event for event in events if event[0] == "progress"]
    assert progress == [("progress", n, 6) for n in range(1, 7)]
    kind, result = events[-1]
    assert kind == "done"
    assert result.parent_tasks_created == 2
    assert result.subtasks_created == 3


def test_run_import_stops_when_list_already_exists(
    project_file: Path,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    google_service.tasklists.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "old", "title": " test project "}]
    }
    monkeypatch.setattr(gui, "get_service", MagicMock(return_value=google_service))
    events: list[tuple] = []

    gui.run_import(gui.load_plan(project_file), events.append)

    assert events[-1] == ("duplicate", "Test Project")
    google_service.tasklists.return_value.insert.assert_not_called()


def test_run_import_reports_sign_in_errors(
    project_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        gui,
        "get_service",
        MagicMock(side_effect=FileNotFoundError("no credentials")),
    )
    events: list[tuple] = []

    gui.run_import(gui.load_plan(project_file), events.append)

    assert events[-1] == ("error", "no credentials")


def test_shorten_path_keeps_short_paths_and_trims_long_ones() -> None:
    assert gui.shorten_path("C:/Notes") == "C:/Notes"
    long_path = "C:/Users/me/" + "deep/" * 20 + "projects"
    shortened = gui.shorten_path(long_path, limit=40)
    assert len(shortened) == 40
    assert shortened.startswith("C:/Users/me")
    assert shortened.endswith("projects")
    assert "..." in shortened


def test_bundled_google_sans_font_and_license_exist() -> None:
    assert gui.asset_path("fonts", gui.FONT_FILE).is_file()
    assert gui.asset_path("fonts", "OFL.txt").is_file()


def test_asset_path_uses_pyinstaller_bundle_when_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gui.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert gui.asset_path("fonts", "x.ttf") == tmp_path / "assets" / "fonts" / "x.ttf"


def test_centered_geometry_accounts_for_display_scaling() -> None:
    assert gui.centered_geometry(900, 540, 1920, 1080) == "900x540+510+270"
    # At 150% scaling the window is 1350x810 physical pixels.
    assert gui.centered_geometry(900, 540, 2560, 1440, 1.5) == "900x540+605+315"
    # Never place the window off-screen on a small display.
    assert gui.centered_geometry(900, 540, 800, 500) == "900x540+0+0"
