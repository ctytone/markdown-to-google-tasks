"""Tests for the Markdown project parser."""

from pathlib import Path
import tempfile
import unittest

from markdown_parser import MarkdownFormatError, parse_markdown, parse_markdown_text


class ParseMarkdownTextTests(unittest.TestCase):
    """Verify parsing and validation of in-memory Markdown."""

    def test_parses_format_and_preserves_order(self) -> None:
        markdown = """# Project Name

## Section Name

- Task 1
- Task 2
- Task 3

## Another Section

- Task A
- Task B
"""
        self.assertEqual(
            parse_markdown_text(markdown),
            {
                "project_name": "Project Name",
                "sections": [
                    {
                        "title": "Section Name",
                        "tasks": ["Task 1", "Task 2", "Task 3"],
                    },
                    {
                        "title": "Another Section",
                        "tasks": ["Task A", "Task B"],
                    },
                ],
            },
        )

    def test_ignores_blank_lines_and_extra_whitespace(self) -> None:
        markdown = """
              #    Whitespace Project

          ##    First Section
             -    First task

        \t- Second task
        """
        self.assertEqual(
            parse_markdown_text(markdown),
            {
                "project_name": "Whitespace Project",
                "sections": [
                    {
                        "title": "First Section",
                        "tasks": ["First task", "Second task"],
                    }
                ],
            },
        )

    def test_preserves_unicode_and_punctuation(self) -> None:
        project = parse_markdown_text(
            "# Café Launch 🚀\n## Research & Design\n- Review naïve approach?"
        )
        self.assertEqual(project["project_name"], "Café Launch 🚀")
        self.assertEqual(
            project["sections"][0]["tasks"], ["Review naïve approach?"]
        )

    def test_allows_section_without_tasks(self) -> None:
        project = parse_markdown_text("# Project\n## Empty Section")
        self.assertEqual(
            project["sections"], [{"title": "Empty Section", "tasks": []}]
        )

    def test_rejects_missing_project_heading(self) -> None:
        with self.assertRaisesRegex(
            MarkdownFormatError, "level-one project heading"
        ):
            parse_markdown_text("")

    def test_rejects_section_before_project(self) -> None:
        with self.assertRaisesRegex(MarkdownFormatError, "section appears before"):
            parse_markdown_text("## Section")

    def test_rejects_task_before_section(self) -> None:
        with self.assertRaisesRegex(MarkdownFormatError, "task appears before"):
            parse_markdown_text("# Project\n- Task")

    def test_rejects_second_project_heading(self) -> None:
        with self.assertRaisesRegex(MarkdownFormatError, "only one"):
            parse_markdown_text("# First\n# Second")

    def test_rejects_unsupported_markdown(self) -> None:
        with self.assertRaisesRegex(MarkdownFormatError, "unsupported"):
            parse_markdown_text("# Project\nOrdinary paragraph")


class ParseMarkdownFileTests(unittest.TestCase):
    """Verify file handling performed by the public file parser."""

    def test_reads_utf8_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.md"
            path.write_text(
                "# Project\n## Section\n- Task\n", encoding="utf-8"
            )
            self.assertEqual(
                parse_markdown(path),
                {
                    "project_name": "Project",
                    "sections": [
                        {"title": "Section", "tasks": ["Task"]}
                    ],
                },
            )

    def test_accepts_uppercase_md_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.MD"
            path.write_text("# Project", encoding="utf-8")
            self.assertEqual(parse_markdown(path)["project_name"], "Project")

    def test_rejects_non_markdown_extension(self) -> None:
        with self.assertRaisesRegex(ValueError, r"\.md file"):
            parse_markdown("project.txt")

    def test_reports_missing_markdown_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.md"
            with self.assertRaises(FileNotFoundError):
                parse_markdown(path)


if __name__ == "__main__":
    unittest.main()
