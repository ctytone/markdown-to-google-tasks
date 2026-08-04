"""Parse project definitions written in the importer's Markdown format.

The supported format intentionally contains only three meaningful constructs:
the first level-one heading supplies the project name, each level-two heading
starts a section, and each hyphen bullet below a section supplies one task.
Blank lines and surrounding whitespace are ignored, while ordering is retained.
Unsupported content raises :class:`MarkdownFormatError`.

This module only parses local data; it does not authenticate or call Google.
"""

from __future__ import annotations

from pathlib import Path
import re

from models import Project, Section


class MarkdownFormatError(ValueError):
    """Indicate that a project file does not follow the supported format."""


_H1_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$")
_H2_PATTERN = re.compile(r"^\s*##\s+(.+?)\s*$")
_BULLET_PATTERN = re.compile(r"^\s*-\s+(.+?)\s*$")


def parse_markdown(file_path: str | Path) -> Project:
    """Read and parse a UTF-8 Markdown project file.

    Args:
        file_path: Path to a file whose extension is ``.md``.

    Returns:
        A project dictionary containing ``project_name`` and an ordered list
        of sections, each with a ``title`` and ordered ``tasks`` list.

    Raises:
        FileNotFoundError: If the path does not exist.
        IsADirectoryError: If the path identifies a directory.
        ValueError: If the path is not a ``.md`` file.
        UnicodeDecodeError: If the file is not valid UTF-8.
        MarkdownFormatError: If the Markdown structure is invalid.
    """
    path = Path(file_path)
    if path.suffix.lower() != ".md":
        raise ValueError(f"Expected a .md file: {path}")
    return parse_markdown_text(path.read_text(encoding="utf-8"))


def parse_markdown_text(markdown: str) -> Project:
    """Parse text using the documented project-file grammar.

    Args:
        markdown: Markdown project content.

    Returns:
        The structured project dictionary.

    Raises:
        MarkdownFormatError: If a required heading is missing, content occurs
            out of order, or a line uses unsupported syntax.
    """
    project_name: str | None = None
    sections: list[Section] = []
    current_section: Section | None = None

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if not line.strip():
            continue

        h2_match = _H2_PATTERN.fullmatch(line)
        h1_match = _H1_PATTERN.fullmatch(line)
        bullet_match = _BULLET_PATTERN.fullmatch(line)

        if h1_match:
            if project_name is not None:
                raise MarkdownFormatError(
                    f"Line {line_number}: only one project heading is allowed."
                )
            project_name = h1_match.group(1)
            continue

        if h2_match:
            if project_name is None:
                raise MarkdownFormatError(
                    f"Line {line_number}: section appears before project heading."
                )
            current_section = Section(title=h2_match.group(1))
            sections.append(current_section)
            continue

        if bullet_match:
            if current_section is None:
                raise MarkdownFormatError(
                    f"Line {line_number}: task appears before a section."
                )
            current_section.tasks.append(bullet_match.group(1))
            continue

        raise MarkdownFormatError(
            f"Line {line_number}: unsupported Markdown content: {line.strip()!r}"
        )

    if project_name is None:
        raise MarkdownFormatError(
            "The Markdown project must contain a level-one project heading."
        )

    return Project(project_name=project_name, sections=sections)
