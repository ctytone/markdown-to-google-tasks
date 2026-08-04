"""Operations performed through the Google Tasks API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Mapping


def create_task_list(service: Any, title: str) -> Mapping[str, Any]:
    """Create and return a Google Tasks list."""
    return service.tasklists().insert(body={"title": title}).execute()


def task_list_exists(service: Any, title: str) -> bool:
    """Return whether a task list exists with the supplied title."""
    response = service.tasklists().list().execute()
    normalized_title = title.strip().lower()
    return any(
        task_list["title"].strip().lower() == normalized_title
        for task_list in response.get("items", [])
    )


def parent_task_exists(
    service: Any,
    task_list_id: str,
    title: str,
) -> bool:
    """Return whether a top-level task with the supplied title exists.

    Completed and hidden tasks are included so an existing task is never
    recreated merely because it is not currently visible. Subtasks with the
    same title do not count as parent-task duplicates.
    """
    return find_parent_task(service, task_list_id, title) is not None


def find_parent_task(
    service: Any,
    task_list_id: str,
    title: str,
) -> Mapping[str, Any] | None:
    """Return a matching top-level task resource, if one exists."""
    normalized_title = title.strip().lower()
    for task in _iter_tasks(service, task_list_id):
        if task.get("parent"):
            continue
        if task.get("title", "").strip().lower() == normalized_title:
            return task
    return None


def subtask_exists(
    service: Any,
    task_list_id: str,
    parent_id: str,
    title: str,
) -> bool:
    """Return whether a matching subtask exists beneath one parent."""
    normalized_title = title.strip().lower()
    return any(
        str(task.get("parent", "")) == parent_id
        and task.get("title", "").strip().lower() == normalized_title
        for task in _iter_tasks(service, task_list_id)
    )


def _iter_tasks(
    service: Any,
    task_list_id: str,
) -> Iterator[Mapping[str, Any]]:
    """Yield every visible, completed, and hidden task across result pages."""
    request_arguments: dict[str, Any] = {
        "tasklist": task_list_id,
        "showCompleted": True,
        "showHidden": True,
    }

    while True:
        response = service.tasks().list(**request_arguments).execute()
        for task in response.get("items", []):
            yield task

        next_page_token = response.get("nextPageToken")
        if not isinstance(next_page_token, str) or not next_page_token:
            return
        request_arguments["pageToken"] = next_page_token


def create_task(
    service: Any,
    task_list_id: str,
    title: str,
    parent_id: str | None = None,
) -> Mapping[str, Any]:
    """Create and return a task in the specified Google Tasks list."""
    task = {"title": title}
    request_arguments = {"tasklist": task_list_id, "body": task}
    if parent_id is not None:
        request_arguments["parent"] = parent_id
    return service.tasks().insert(**request_arguments).execute()
