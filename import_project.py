"""Command-line entry point for the Google Tasks importer."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from auth import get_service
from execution_engine import execute_plan, has_duplicate_task_list
from execution_plan import build_execution_plan
from markdown_parser import MarkdownFormatError, parse_markdown
from utils import (
    confirm_action,
    print_cancelled,
    print_connection_success,
    print_dry_run_result,
    print_duplicate_error,
    print_error,
    print_execution_progress,
    print_execution_result,
    print_execution_start,
    print_plan_preview,
    print_verbose,
)


def _parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the importer."""
    parser = argparse.ArgumentParser(
        description=(
            "Preview or import a Markdown project into Google Tasks."
        ),
        epilog=(
            "examples:\n"
            "  python import_project.py project.md --dry-run\n"
            "  python import_project.py project.md --execute\n"
            "  python import_project.py project.md --execute --force"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "project_file",
        help="Markdown project file to preview or import",
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="preview the plan without prompts or Google API calls",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="execute the plan against Google Tasks",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="execute without the confirmation prompt",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show additional workflow details",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Parse a Markdown project and run the Google Tasks import workflow."""
    options = _parse_arguments(arguments)

    try:
        project = parse_markdown(options.project_file)
    except (OSError, UnicodeError, ValueError, MarkdownFormatError) as error:
        print_error(str(error))
        return 1

    plan = build_execution_plan(project)
    print_verbose(
        f"Parsed project and built {len(plan)} operations.",
        enabled=options.verbose,
    )
    print_plan_preview(
        plan,
        options.project_file,
        safe_mode=not options.force,
        dry_run=options.dry_run,
    )

    if options.dry_run:
        print_verbose(
            "Dry run selected; Google API access is disabled.",
            enabled=options.verbose,
        )
        print_dry_run_result()
        return 0

    print_verbose(
        "Authenticating with Google Tasks.",
        enabled=options.verbose,
    )
    service = get_service()
    print_connection_success()

    if has_duplicate_task_list(service, plan):
        print_duplicate_error()
        return 0

    if not confirm_action("Continue", force=options.force):
        print_cancelled()
        return 0

    print_execution_start()
    try:
        result = execute_plan(
            service,
            plan,
            progress_callback=print_execution_progress,
        )
    except Exception as error:
        print_error(f"Execution failed: {error}")
        return 1

    print_execution_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
