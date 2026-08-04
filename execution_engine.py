"""Execute validated execution plans through the Google Tasks API.

This module is the only layer that translates execution-plan operations into
Google Tasks API calls. Operations run sequentially, and execution stops
immediately if an operation fails.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Mapping

from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    CreateTaskListOperation,
    ExecutionPlan,
    Operation,
)
from tasks_api import (
    create_task,
    create_task_list,
    find_parent_task,
    subtask_exists,
    task_list_exists,
)


@dataclass(frozen=True)
class ExecutionProgress:
    """Describe progress before or after one planned operation."""

    current: int
    total: int
    operation: Operation
    completed: bool
    skipped: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    """Summarize the successfully completed execution of a plan."""

    task_list: Mapping[str, Any]
    task_lists_created: int
    parent_tasks_created: int
    subtasks_created: int
    parent_tasks_skipped: int
    subtasks_skipped: int
    elapsed_seconds: float

    @property
    def operations_skipped(self) -> int:
        """Return the total number of skipped create operations."""
        return self.parent_tasks_skipped + self.subtasks_skipped


ProgressCallback = Callable[[ExecutionProgress], None]


def has_duplicate_task_list(service: Any, plan: ExecutionPlan) -> bool:
    """Return whether the plan's destination task list already exists."""
    return task_list_exists(service, plan.project_name)


def execute_plan(
    service: Any,
    plan: ExecutionPlan,
    progress_callback: ProgressCallback | None = None,
) -> ExecutionResult:
    """Execute supported operations sequentially in their planned order.

    Args:
        service: Authenticated Google Tasks API service.
        plan: Ordered execution plan to run.
        progress_callback: Optional receiver called immediately before and
            after every successfully completed operation.

    Returns:
        Counts, timing, and the created task-list API resource.

    Raises:
        RuntimeError: If a parent task appears before task-list creation.
        TypeError: If the plan contains an operation unsupported by this
            milestone.
        KeyError: If Google does not return an ID for the created task list.
        Exception: Any Google API exception raised while executing an
            operation. Later operations are not attempted.
    """
    started_at = perf_counter()
    task_list: Mapping[str, Any] | None = None
    task_list_id: str | None = None
    task_lists_created = 0
    parent_tasks_created = 0
    subtasks_created = 0
    parent_tasks_skipped = 0
    subtasks_skipped = 0
    parent_task_ids: dict[str, str] = {}
    known_subtasks: set[tuple[str, str]] = set()
    total_operations = len(plan)

    for operation_number, operation in enumerate(plan, start=1):
        _notify(
            progress_callback,
            ExecutionProgress(
                current=operation_number,
                total=total_operations,
                operation=operation,
                completed=False,
            ),
        )

        if isinstance(operation, CreateTaskListOperation):
            task_list = create_task_list(service, operation.title)
            task_list_id = str(task_list["id"])
            task_lists_created += 1
        elif isinstance(operation, CreateParentTaskOperation):
            if task_list_id is None:
                raise RuntimeError(
                    "A task list must be created before parent tasks."
                )
            normalized_title = operation.title.strip().lower()
            if normalized_title in parent_task_ids:
                parent_tasks_skipped += 1
                _notify(
                    progress_callback,
                    ExecutionProgress(
                        current=operation_number,
                        total=total_operations,
                        operation=operation,
                        completed=True,
                        skipped=True,
                    ),
                )
                continue

            existing_parent = find_parent_task(
                service,
                task_list_id,
                operation.title,
            )
            if existing_parent is not None:
                parent_task_ids[normalized_title] = str(
                    existing_parent["id"]
                )
                parent_tasks_skipped += 1
                _notify(
                    progress_callback,
                    ExecutionProgress(
                        current=operation_number,
                        total=total_operations,
                        operation=operation,
                        completed=True,
                        skipped=True,
                    ),
                )
                continue

            parent_task = create_task(
                service,
                task_list_id,
                operation.title,
            )
            parent_task_ids[normalized_title] = str(parent_task["id"])
            parent_tasks_created += 1
        elif isinstance(operation, CreateSubtaskOperation):
            if task_list_id is None:
                raise RuntimeError(
                    "A task list must be created before subtasks."
                )
            parent_key = operation.parent_title.strip().lower()
            try:
                parent_id = parent_task_ids[parent_key]
            except KeyError as error:
                raise RuntimeError(
                    "A parent task must be resolved before its subtasks: "
                    f"{operation.parent_title}"
                ) from error

            subtask_key = (parent_id, operation.title.strip().lower())
            if (
                subtask_key in known_subtasks
                or subtask_exists(
                    service,
                    task_list_id,
                    parent_id,
                    operation.title,
                )
            ):
                known_subtasks.add(subtask_key)
                subtasks_skipped += 1
                _notify(
                    progress_callback,
                    ExecutionProgress(
                        current=operation_number,
                        total=total_operations,
                        operation=operation,
                        completed=True,
                        skipped=True,
                    ),
                )
                continue

            create_task(
                service,
                task_list_id,
                operation.title,
                parent_id=parent_id,
            )
            known_subtasks.add(subtask_key)
            subtasks_created += 1
        else:
            raise TypeError(
                f"Unsupported execution operation: {operation!r}"
            )

        _notify(
            progress_callback,
            ExecutionProgress(
                current=operation_number,
                total=total_operations,
                operation=operation,
                completed=True,
            ),
        )

    if task_list is None:
        raise RuntimeError("The execution plan did not create a task list.")

    return ExecutionResult(
        task_list=task_list,
        task_lists_created=task_lists_created,
        parent_tasks_created=parent_tasks_created,
        subtasks_created=subtasks_created,
        parent_tasks_skipped=parent_tasks_skipped,
        subtasks_skipped=subtasks_skipped,
        elapsed_seconds=perf_counter() - started_at,
    )


def _notify(
    callback: ProgressCallback | None,
    progress: ExecutionProgress,
) -> None:
    """Send progress to a callback when one was supplied."""
    if callback is not None:
        callback(progress)
