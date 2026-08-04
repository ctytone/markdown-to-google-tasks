"""Unit tests for non-destructive Google Tasks API helpers."""

import unittest
from unittest.mock import MagicMock, call

from tasks_api import parent_task_exists, subtask_exists


class ParentTaskExistsTests(unittest.TestCase):
    """Verify parent-task duplicate detection."""

    def setUp(self) -> None:
        """Create a fake Google Tasks service."""
        self.service = MagicMock()

    def test_matches_parent_title_case_insensitively(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "task-id", "title": "  PLANNING  "}]
        }

        self.assertTrue(
            parent_task_exists(self.service, "list-id", "Planning")
        )
        self.service.tasks.return_value.list.assert_called_once_with(
            tasklist="list-id",
            showCompleted=True,
            showHidden=True,
        )

    def test_ignores_subtask_with_same_title(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "child-id",
                    "title": "Planning",
                    "parent": "parent-id",
                }
            ]
        }

        self.assertFalse(
            parent_task_exists(self.service, "list-id", "Planning")
        )

    def test_checks_all_result_pages_in_order(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.side_effect = [
            {
                "items": [{"id": "other", "title": "Other"}],
                "nextPageToken": "page-2",
            },
            {"items": [{"id": "match", "title": "Planning"}]},
        ]

        self.assertTrue(
            parent_task_exists(self.service, "list-id", "Planning")
        )
        self.assertEqual(
            self.service.tasks.return_value.list.call_args_list,
            [
                call(
                    tasklist="list-id",
                    showCompleted=True,
                    showHidden=True,
                ),
                call(
                    tasklist="list-id",
                    showCompleted=True,
                    showHidden=True,
                    pageToken="page-2",
                ),
            ],
        )


class SubtaskExistsTests(unittest.TestCase):
    """Verify duplicate detection is scoped to the correct parent."""

    def setUp(self) -> None:
        """Create a fake Google Tasks service."""
        self.service = MagicMock()

    def test_matches_title_only_beneath_requested_parent(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "other-child",
                    "title": "Create folder",
                    "parent": "other-parent",
                },
                {
                    "id": "matching-child",
                    "title": "  CREATE FOLDER ",
                    "parent": "planning-id",
                },
            ]
        }

        self.assertTrue(
            subtask_exists(
                self.service,
                "list-id",
                "planning-id",
                "Create folder",
            )
        )

    def test_same_title_under_different_parent_is_not_duplicate(self) -> None:
        self.service.tasks.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "other-child",
                    "title": "Create folder",
                    "parent": "other-parent",
                }
            ]
        }

        self.assertFalse(
            subtask_exists(
                self.service,
                "list-id",
                "planning-id",
                "Create folder",
            )
        )


if __name__ == "__main__":
    unittest.main()
