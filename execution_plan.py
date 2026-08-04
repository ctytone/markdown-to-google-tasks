"""Build ordered execution plans from project models."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Union, overload

from models import Project


@dataclass(frozen=True)
class CreateTaskListOperation:
    """Describe creation of the project's Google Tasks list."""

    title: str


@dataclass(frozen=True)
class CreateParentTaskOperation:
    """Describe creation of one section as a top-level task."""

    title: str


@dataclass(frozen=True)
class CreateSubtaskOperation:
    """Describe creation of a task beneath a named parent task."""

    title: str
    parent_title: str


Operation = Union[
    CreateTaskListOperation,
    CreateParentTaskOperation,
    CreateSubtaskOperation,
]


@dataclass(frozen=True)
class ExecutionPlan(Sequence[Operation]):
    """An immutable, ordered collection of planned Google Tasks operations."""

    project_name: str
    operations: tuple[Operation, ...]

    @overload
    def __getitem__(self, index: int) -> Operation:
        ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Operation, ...]:
        ...

    def __getitem__(
        self, index: int | slice
    ) -> Operation | tuple[Operation, ...]:
        """Return one operation or an operation slice."""
        return self.operations[index]

    def __iter__(self) -> Iterator[Operation]:
        """Iterate through operations in execution order."""
        return iter(self.operations)

    def __len__(self) -> int:
        """Return the number of planned operations."""
        return len(self.operations)

    @property
    def task_list_count(self) -> int:
        """Return the number of task-list creation operations."""
        return sum(
            isinstance(operation, CreateTaskListOperation)
            for operation in self
        )

    @property
    def parent_task_count(self) -> int:
        """Return the number of parent-task creation operations."""
        return sum(
            isinstance(operation, CreateParentTaskOperation)
            for operation in self
        )

    @property
    def subtask_count(self) -> int:
        """Return the number of subtask creation operations."""
        return sum(
            isinstance(operation, CreateSubtaskOperation)
            for operation in self
        )


def build_execution_plan(project: Project) -> ExecutionPlan:
    """Convert a project model into an ordered execution plan."""
    operations: list[Operation] = [
        CreateTaskListOperation(title=project.project_name)
    ]
    for section in project.sections:
        operations.append(CreateParentTaskOperation(title=section.title))
        operations.extend(
            CreateSubtaskOperation(
                title=task,
                parent_title=section.title,
            )
            for task in section.tasks
        )
    return ExecutionPlan(
        project_name=project.project_name,
        operations=tuple(operations),
    )
