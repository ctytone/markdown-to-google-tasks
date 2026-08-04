"""Unit tests for project-to-execution-plan conversion."""

import unittest

from execution_plan import (
    CreateParentTaskOperation,
    CreateSubtaskOperation,
    CreateTaskListOperation,
    ExecutionPlan,
    build_execution_plan,
)
from models import Project, Section


class ProjectModelTests(unittest.TestCase):
    """Verify the explicit project domain model."""

    def test_dataclasses_preserve_order_and_mapping_compatibility(self) -> None:
        project = Project(
            project_name="Importer",
            sections=[
                Section(title="First", tasks=["A", "B"]),
                Section(title="Second", tasks=["C"]),
            ],
        )

        self.assertEqual(project.project_name, "Importer")
        self.assertEqual(
            [section.title for section in project.sections],
            ["First", "Second"],
        )
        self.assertEqual(project["sections"][0]["tasks"], ["A", "B"])
        self.assertEqual(
            project,
            {
                "project_name": "Importer",
                "sections": [
                    {"title": "First", "tasks": ["A", "B"]},
                    {"title": "Second", "tasks": ["C"]},
                ],
            },
        )


class ExecutionPlannerTests(unittest.TestCase):
    """Verify plan contents and operation ordering."""

    def setUp(self) -> None:
        """Create an ordered model representative of parsed Markdown."""
        self.project = Project(
            project_name="GroupMe Calendar Importer",
            sections=[
                Section(title="Planning", tasks=["Create folder"]),
                Section(title="Google Setup", tasks=["Enable API"]),
                Section(title="Development", tasks=["Build UI"]),
            ],
        )

    def test_plan_contains_task_list_then_each_parent_task(self) -> None:
        plan = build_execution_plan(self.project)

        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(plan.project_name, "GroupMe Calendar Importer")
        self.assertEqual(
            plan.operations,
            (
                CreateTaskListOperation("GroupMe Calendar Importer"),
                CreateParentTaskOperation("Planning"),
                CreateSubtaskOperation("Create folder", "Planning"),
                CreateParentTaskOperation("Google Setup"),
                CreateSubtaskOperation("Enable API", "Google Setup"),
                CreateParentTaskOperation("Development"),
                CreateSubtaskOperation("Build UI", "Development"),
            ),
        )

    def test_plan_preserves_section_order(self) -> None:
        plan = build_execution_plan(self.project)

        self.assertEqual(
            [operation.title for operation in plan],
            [
                "GroupMe Calendar Importer",
                "Planning",
                "Create folder",
                "Google Setup",
                "Enable API",
                "Development",
                "Build UI",
            ],
        )

    def test_subtasks_follow_their_parent_in_markdown_order(self) -> None:
        plan = build_execution_plan(self.project)

        subtasks = [
            operation
            for operation in plan
            if isinstance(operation, CreateSubtaskOperation)
        ]
        self.assertEqual(
            subtasks,
            [
                CreateSubtaskOperation("Create folder", "Planning"),
                CreateSubtaskOperation("Enable API", "Google Setup"),
                CreateSubtaskOperation("Build UI", "Development"),
            ],
        )

    def test_empty_project_still_plans_task_list_creation(self) -> None:
        plan = build_execution_plan(Project(project_name="Empty"))

        self.assertEqual(
            plan.operations,
            (CreateTaskListOperation("Empty"),),
        )


if __name__ == "__main__":
    unittest.main()
