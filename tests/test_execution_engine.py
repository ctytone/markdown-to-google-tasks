"""Integration tests for sequential execution-plan processing."""

import unittest
from unittest.mock import MagicMock, call, patch

import execution_engine
from execution_engine import ExecutionProgress, execute_plan
from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    CreateTaskListOperation,
    ExecutionPlan,
)


class ExecutionEngineTests(unittest.TestCase):
    """Verify API dispatch, ordering, progress, and execution results."""

    def setUp(self) -> None:
        """Create a complete supported plan and fake API service."""
        self.plan = ExecutionPlan(
            project_name="Project",
            operations=(
                CreateTaskListOperation("Project"),
                CreateParentTaskOperation("Planning"),
                CreateParentTaskOperation("Development"),
            ),
        )
        self.service = MagicMock()
        self.service.tasklists.return_value.insert.return_value.execute.return_value = {
            "id": "list-id",
            "title": "Project",
        }
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            {"id": "parent-1", "title": "Planning"},
            {"id": "parent-2", "title": "Development"},
        ]

    def test_executes_supported_operations_sequentially(self) -> None:
        with patch.object(
            execution_engine,
            "perf_counter",
            side_effect=[10.0, 10.41],
        ):
            result = execute_plan(self.service, self.plan)

        self.service.tasklists.return_value.insert.assert_called_once_with(
            body={"title": "Project"}
        )
        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(tasklist="list-id", body={"title": "Planning"}),
                call(tasklist="list-id", body={"title": "Development"}),
            ],
        )
        self.assertEqual(result.task_lists_created, 1)
        self.assertEqual(result.parent_tasks_created, 2)
        self.assertEqual(result.parent_tasks_skipped, 0)
        self.assertAlmostEqual(result.elapsed_seconds, 0.41)

    def test_reports_before_and_after_progress_in_order(self) -> None:
        events: list[ExecutionProgress] = []

        execute_plan(self.service, self.plan, progress_callback=events.append)

        self.assertEqual(
            [
                (event.current, event.total, event.completed)
                for event in events
            ],
            [
                (1, 3, False),
                (1, 3, True),
                (2, 3, False),
                (2, 3, True),
                (3, 3, False),
                (3, 3, True),
            ],
        )
        self.assertEqual(
            [events[index].operation for index in (0, 2, 4)],
            list(self.plan.operations),
        )

    def test_creates_subtask_under_resolved_parent(self) -> None:
        subtask_plan = ExecutionPlan(
            project_name="Project",
            operations=(
                CreateTaskListOperation("Project"),
                CreateParentTaskOperation("Parent"),
                CreateSubtaskOperation("Child", "Parent"),
            ),
        )
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            {"id": "parent-id", "title": "Parent"},
            {"id": "child-id", "title": "Child", "parent": "parent-id"},
        ]

        result = execute_plan(self.service, subtask_plan)

        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(tasklist="list-id", body={"title": "Parent"}),
                call(
                    tasklist="list-id",
                    body={"title": "Child"},
                    parent="parent-id",
                ),
            ],
        )
        self.assertEqual(result.subtasks_created, 1)
        self.assertEqual(result.subtasks_skipped, 0)

    def test_skips_existing_subtask_under_same_parent(self) -> None:
        subtask_plan = ExecutionPlan(
            project_name="Project",
            operations=(
                CreateTaskListOperation("Project"),
                CreateParentTaskOperation("Parent"),
                CreateSubtaskOperation("Existing child", "Parent"),
                CreateSubtaskOperation("New child", "Parent"),
            ),
        )
        self.service.tasks.return_value.list.return_value.execute.side_effect = [
            {"items": []},
            {
                "items": [
                    {
                        "id": "existing-child",
                        "title": "Existing child",
                        "parent": "parent-id",
                    }
                ]
            },
            {"items": []},
        ]
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            {"id": "parent-id", "title": "Parent"},
            {"id": "new-child", "title": "New child"},
        ]
        events: list[ExecutionProgress] = []

        result = execute_plan(
            self.service,
            subtask_plan,
            progress_callback=events.append,
        )

        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(tasklist="list-id", body={"title": "Parent"}),
                call(
                    tasklist="list-id",
                    body={"title": "New child"},
                    parent="parent-id",
                ),
            ],
        )
        self.assertEqual(result.subtasks_created, 1)
        self.assertEqual(result.subtasks_skipped, 1)
        skipped = [event for event in events if event.skipped]
        self.assertEqual(skipped[0].operation.title, "Existing child")

    def test_stops_when_an_api_operation_fails(self) -> None:
        self.service.tasks.return_value.insert.return_value.execute.side_effect = [
            RuntimeError("API failure"),
            {"id": "parent-2"},
        ]

        with self.assertRaisesRegex(RuntimeError, "API failure"):
            execute_plan(self.service, self.plan)

        self.assertEqual(
            self.service.tasks.return_value.insert.call_count,
            1,
        )

    def test_skips_existing_parent_without_modifying_it(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.side_effect = [
            {"items": [{"id": "existing", "title": " planning "}]},
            {"items": []},
        ]
        events: list[ExecutionProgress] = []

        result = execute_plan(
            self.service,
            self.plan,
            progress_callback=events.append,
        )

        self.assertEqual(
            self.service.tasks.return_value.insert.call_args_list,
            [
                call(
                    tasklist="list-id",
                    body={"title": "Development"},
                )
            ],
        )
        self.assertEqual(result.parent_tasks_created, 1)
        self.assertEqual(result.parent_tasks_skipped, 1)
        skipped_events = [event for event in events if event.skipped]
        self.assertEqual(len(skipped_events), 1)
        self.assertEqual(skipped_events[0].operation.title, "Planning")

    def test_skips_repeated_parent_titles_within_same_plan(self) -> None:
        repeated_plan = ExecutionPlan(
            project_name="Project",
            operations=(
                CreateTaskListOperation("Project"),
                CreateParentTaskOperation("Planning"),
                CreateParentTaskOperation(" planning "),
            ),
        )

        result = execute_plan(self.service, repeated_plan)

        self.service.tasks.return_value.insert.assert_called_once_with(
            tasklist="list-id",
            body={"title": "Planning"},
        )
        self.assertEqual(
            self.service.tasks.return_value.list.call_count,
            1,
        )
        self.assertEqual(result.parent_tasks_created, 1)
        self.assertEqual(result.parent_tasks_skipped, 1)


if __name__ == "__main__":
    unittest.main()
