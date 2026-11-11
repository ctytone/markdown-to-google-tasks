"""Integration tests for plan-driven Markdown importing."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

import import_project


class MarkdownImporterIntegrationTests(unittest.TestCase):
    """Verify the importer plans parsed Markdown before taking action."""

    def setUp(self) -> None:
        """Create representative Markdown and a fake Tasks API service."""
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.markdown_path = Path(self.temporary_directory.name) / "project.md"
        self.markdown_path.write_text(
            """# GroupMe Calendar Importer

## Planning
- Create project folder
- Open project folder

## Development
- Build UI
- Connect API
""",
            encoding="utf-8",
        )

        self.service = MagicMock()
        self.service.tasklists.return_value.list.return_value.execute.return_value = {
            "items": []
        }
        self.service.tasklists.return_value.insert.return_value.execute.return_value = {
            "id": "task-list-id",
            "title": "GroupMe Calendar Importer",
        }
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            {"id": "planning-id", "title": "Planning"},
            {
                "id": "create-folder-id",
                "title": "Create project folder",
                "parent": "planning-id",
            },
            {
                "id": "open-folder-id",
                "title": "Open project folder",
                "parent": "planning-id",
            },
            {"id": "development-id", "title": "Development"},
            {
                "id": "build-ui-id",
                "title": "Build UI",
                "parent": "development-id",
            },
            {
                "id": "connect-api-id",
                "title": "Connect API",
                "parent": "development-id",
            },
        ]

    def run_import(
        self,
        *,
        dry_run: bool,
        confirmation: str = "y",
        force: bool = False,
        verbose: bool = False,
    ) -> tuple[int, str]:
        """Run the importer with the real parser and mocked API service."""
        output = StringIO()
        get_service = MagicMock(return_value=self.service)
        user_input = MagicMock(return_value=confirmation)
        arguments = [
            str(self.markdown_path),
            "--dry-run" if dry_run else "--execute",
        ]
        if force:
            arguments.append("--force")
        if verbose:
            arguments.append("--verbose")
        with (
            patch.object(import_project, "get_service", get_service),
            patch("builtins.input", user_input),
            redirect_stdout(output),
        ):
            status = import_project.main(arguments)
        self.get_service = get_service
        self.user_input = user_input
        return status, output.getvalue()

    def test_dry_run_prints_execution_plan_without_creating(self) -> None:
        status, output = self.run_import(dry_run=True)

        self.assertEqual(status, 0)
        self.assertIn("Project", output)
        self.assertIn("GroupMe Calendar Importer", output)
        self.assertIn(
            "[1] Create Task List\n"
            "    GroupMe Calendar Importer",
            output,
        )
        self.assertIn(
            "[2] Create Parent Task\n    Planning",
            output,
        )
        self.assertIn(
            "    [3] Create Subtask\n"
            "        Create project folder",
            output,
        )
        self.assertIn(
            "[5] Create Parent Task\n    Development",
            output,
        )
        self.assertIn(
            "    [7] Create Subtask\n        Connect API",
            output,
        )
        self.assertIn("Subtasks    : 4", output)
        self.assertIn("Nothing has been created.", output)
        output.encode("ascii")
        self.user_input.assert_not_called()
        self.get_service.assert_not_called()
        self.service.tasklists.return_value.insert.assert_not_called()
        self.service.tasks.assert_not_called()

    def test_normal_run_executes_planned_operations_in_order(self) -> None:
        status, output = self.run_import(dry_run=False)

        self.assertEqual(status, 0)
        self.user_input.assert_called_once()
        self.service.tasklists.return_value.insert.assert_called_once_with(
            body={"title": "GroupMe Calendar Importer"}
        )
        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(
                    tasklist="task-list-id",
                    body={"title": "Planning"},
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Create project folder"},
                    parent="planning-id",
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Open project folder"},
                    parent="planning-id",
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Development"},
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Build UI"},
                    parent="development-id",
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Connect API"},
                    parent="development-id",
                ),
            ],
        )
        self.assertIn("Completed Successfully", output)
        self.assertIn("[1/7] Create Task List...\n[OK]", output)
        self.assertIn("Task Lists : 1", output)
        self.assertIn("Parent Tasks: 2", output)
        self.assertIn("Subtasks   : 4", output)
        self.assertIn("Skipped    : 0", output)
        output.encode("ascii")

    def test_existing_parent_is_skipped_and_reported(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": "planning-id", "title": "Planning"}]},
            {
                "items": [
                    {
                        "id": "create-folder-id",
                        "title": "Create project folder",
                        "parent": "planning-id",
                    }
                ]
            },
            {"items": []},
            {"items": []},
            {"items": []},
            {"items": []},
        ]
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            {
                "id": "open-folder-id",
                "title": "Open project folder",
            },
            {"id": "development-id", "title": "Development"},
            {"id": "build-ui-id", "title": "Build UI"},
            {"id": "connect-api-id", "title": "Connect API"},
        ]

        status, output = self.run_import(dry_run=False)

        self.assertEqual(status, 0)
        self.assertIn(
            "[SKIP] Parent task already exists:\nPlanning",
            output,
        )
        self.assertIn(
            "[SKIP] Subtask already exists:\nCreate project folder",
            output,
        )
        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(
                    tasklist="task-list-id",
                    body={"title": "Open project folder"},
                    parent="planning-id",
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Development"},
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Build UI"},
                    parent="development-id",
                ),
                call(
                    tasklist="task-list-id",
                    body={"title": "Connect API"},
                    parent="development-id",
                ),
            ],
        )
        self.assertIn("Parent Tasks: 1", output)
        self.assertIn("Subtasks   : 3", output)
        self.assertIn("Skipped    : 2", output)

    def test_duplicate_name_from_markdown_prevents_execution(self) -> None:
        self.service.tasklists.return_value.list.return_value.execute.return_value = {
            "items": [{"title": " groupme calendar importer "}]
        }

        status, output = self.run_import(dry_run=False)

        self.assertEqual(status, 0)
        self.assertIn("Task list already exists.", output)
        self.service.tasklists.return_value.insert.assert_not_called()
        self.service.tasks.assert_not_called()

    def test_safe_mode_cancellation_prevents_execution(self) -> None:
        status, output = self.run_import(
            dry_run=False,
            confirmation="n",
        )

        self.assertEqual(status, 0)
        self.assertIn("Cancelled.", output)
        self.service.tasklists.return_value.insert.assert_not_called()
        self.service.tasks.assert_not_called()

    def test_force_execution_skips_confirmation_prompt(self) -> None:
        output = StringIO()
        with (
            patch.object(
                import_project,
                "get_service",
                return_value=self.service,
            ),
            patch("builtins.input") as user_input,
            redirect_stdout(output),
        ):
            status = import_project.main(
                [str(self.markdown_path), "--execute", "--force"]
            )

        self.assertEqual(status, 0)
        user_input.assert_not_called()
        self.service.tasklists.return_value.insert.assert_called_once()

    def test_verbose_mode_prints_workflow_information(self) -> None:
        status, output = self.run_import(
            dry_run=True,
            verbose=True,
        )

        self.assertEqual(status, 0)
        self.assertIn("[INFO] Parsed project and built", output)
        self.assertIn("Google API access is disabled.", output)

    def test_sign_in_failure_reports_error_without_traceback(self) -> None:
        output = StringIO()
        with (
            patch.object(
                import_project,
                "get_service",
                side_effect=FileNotFoundError("credentials.json missing"),
            ),
            redirect_stdout(output),
        ):
            status = import_project.main(
                [str(self.markdown_path), "--execute", "--force"]
            )

        self.assertEqual(status, 1)
        self.assertIn(
            "[ERROR] Google sign-in failed: credentials.json missing",
            output.getvalue(),
        )

    def test_invalid_markdown_stops_before_planning_or_connection(self) -> None:
        self.markdown_path.write_text("## Missing project", encoding="utf-8")

        with (
            patch.object(import_project, "get_service") as get_service,
            patch.object(import_project, "build_execution_plan") as planner,
            redirect_stdout(StringIO()),
        ):
            status = import_project.main(
                [str(self.markdown_path), "--dry-run"]
            )

        self.assertEqual(status, 1)
        planner.assert_not_called()
        get_service.assert_not_called()


class CommandLineArgumentTests(unittest.TestCase):
    """Verify required modes and optional command-line flags."""

    def test_requires_dry_run_or_execute_mode(self) -> None:
        error_output = StringIO()

        with (
            self.assertRaises(SystemExit) as exit_context,
            redirect_stderr(error_output),
        ):
            import_project._parse_arguments(["project.md"])

        self.assertEqual(exit_context.exception.code, 2)
        self.assertIn("usage:", error_output.getvalue())

    def test_parses_execute_force_and_verbose_flags(self) -> None:
        options = import_project._parse_arguments(
            ["project.md", "--execute", "--force", "--verbose"]
        )

        self.assertEqual(options.project_file, "project.md")
        self.assertTrue(options.execute)
        self.assertFalse(options.dry_run)
        self.assertTrue(options.force)
        self.assertTrue(options.verbose)

    def test_rejects_both_execution_modes(self) -> None:
        with (
            self.assertRaises(SystemExit),
            redirect_stderr(StringIO()),
        ):
            import_project._parse_arguments(
                ["project.md", "--dry-run", "--execute"]
            )

    def test_help_describes_all_release_arguments(self) -> None:
        help_output = StringIO()

        with (
            self.assertRaises(SystemExit) as exit_context,
            redirect_stdout(help_output),
        ):
            import_project._parse_arguments(["--help"])

        self.assertEqual(exit_context.exception.code, 0)
        rendered_help = help_output.getvalue()
        self.assertIn("project_file", rendered_help)
        self.assertIn("--dry-run", rendered_help)
        self.assertIn("--execute", rendered_help)
        self.assertIn("--force", rendered_help)
        self.assertIn("--verbose", rendered_help)
        self.assertIn("examples:", rendered_help)


if __name__ == "__main__":
    unittest.main()
