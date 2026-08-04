"""ASCII-only console presentation helpers for the importer."""

from pathlib import Path

from execution_engine import ExecutionProgress, ExecutionResult
from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    CreateTaskListOperation,
    ExecutionPlan,
    Operation,
)

PRIMARY_SEPARATOR = "=" * 50
SECONDARY_SEPARATOR = "-" * 50


def operation_name(operation: Operation) -> str:
    """Return the user-facing name of an execution operation."""
    if isinstance(operation, CreateTaskListOperation):
        return "Create Task List"
    if isinstance(operation, CreateParentTaskOperation):
        return "Create Parent Task"
    if isinstance(operation, CreateSubtaskOperation):
        return "Create Subtask"
    raise TypeError(f"Unsupported execution operation: {operation!r}")


def print_plan_preview(
    plan: ExecutionPlan,
    markdown_file: str | Path,
    *,
    safe_mode: bool,
    dry_run: bool,
) -> None:
    """Print a complete, consistently formatted execution-plan preview."""
    print(PRIMARY_SEPARATOR)
    print("Google Tasks Importer")
    print(PRIMARY_SEPARATOR)
    print()
    print(f"Project       : {plan.project_name}")
    print(f"Markdown File : {markdown_file}")
    print(f"Mode          : {'Dry Run' if dry_run else 'Execute'}")
    confirmation = "Skipped" if not safe_mode else "Required"
    if dry_run:
        confirmation = "Not required"
    print(f"Confirmation  : {confirmation}")
    print()
    print(PRIMARY_SEPARATOR)
    print("Execution Plan")
    print(PRIMARY_SEPARATOR)

    for operation_number, operation in enumerate(plan, start=1):
        if isinstance(operation, CreateSubtaskOperation):
            print(f"    [{operation_number}] {operation_name(operation)}")
            print(f"        {operation.title}")
        else:
            print(f"[{operation_number}] {operation_name(operation)}")
            print(f"    {operation.title}")
        print()

    print(SECONDARY_SEPARATOR)
    print("Summary")
    print(SECONDARY_SEPARATOR)
    print()
    print(f"Task Lists  : {plan.task_list_count}")
    print(f"Parent Tasks: {plan.parent_task_count}")
    print(f"Subtasks    : {plan.subtask_count}")
    print(f"Operations  : {len(plan)}")
    print()
    print(PRIMARY_SEPARATOR)


def print_connection_success() -> None:
    """Print a compact successful-connection status."""
    print()
    print("[OK] Connected to Google Tasks.")


def print_duplicate_error() -> None:
    """Print the non-destructive duplicate-list result."""
    print()
    print("[ERROR] Task list already exists.")
    print("No operations were executed.")
    print(PRIMARY_SEPARATOR)


def print_cancelled() -> None:
    """Print a clean cancellation result."""
    print()
    print("Cancelled. No operations were executed.")
    print(PRIMARY_SEPARATOR)


def print_dry_run_result() -> None:
    """Print the final result for a dry run."""
    print("Nothing has been created.")
    print(PRIMARY_SEPARATOR)


def print_execution_start() -> None:
    """Print the real-execution section heading."""
    print()
    print(SECONDARY_SEPARATOR)
    print("Executing")
    print(SECONDARY_SEPARATOR)
    print()


def print_execution_progress(progress: ExecutionProgress) -> None:
    """Print one before/after execution progress event."""
    if progress.skipped:
        task_type = (
            "Subtask"
            if isinstance(progress.operation, CreateSubtaskOperation)
            else "Parent task"
        )
        print(f"[SKIP] {task_type} already exists:")
        print(progress.operation.title)
        return
    if progress.completed:
        print("[OK]")
        return
    print(
        f"[{progress.current}/{progress.total}] "
        f"{operation_name(progress.operation)}..."
    )


def print_execution_result(result: ExecutionResult) -> None:
    """Print a successful execution summary."""
    print()
    print(SECONDARY_SEPARATOR)
    print("Completed Successfully")
    print(SECONDARY_SEPARATOR)
    print()
    print("Created")
    print()
    print(f"Task Lists : {result.task_lists_created}")
    print(f"Parent Tasks: {result.parent_tasks_created}")
    print(f"Subtasks   : {result.subtasks_created}")
    print(f"Skipped    : {result.operations_skipped}")
    print(f"Elapsed    : {result.elapsed_seconds:.2f} sec")
    print()
    print(PRIMARY_SEPARATOR)


def print_error(message: str) -> None:
    """Print a consistently formatted error."""
    print(PRIMARY_SEPARATOR)
    print("Google Tasks Importer")
    print(PRIMARY_SEPARATOR)
    print()
    print(f"[ERROR] {message}")
    print()
    print(PRIMARY_SEPARATOR)


def confirm_action(message: str, *, force: bool = False) -> bool:
    """Request confirmation unless force mode bypasses prompts."""
    if force:
        return True
    return input(f"\n{message} (y/n): ").strip().lower() == "y"


def print_verbose(message: str, *, enabled: bool) -> None:
    """Print an informational message when verbose output is enabled."""
    if enabled:
        print(f"[INFO] {message}")

