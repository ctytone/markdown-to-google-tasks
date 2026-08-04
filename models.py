"""Domain models for parsed Google Tasks projects.

The models expose lightweight mapping behavior for compatibility with existing
callers that use dictionary indexing. Their canonical representation is still
an explicit dataclass model with named attributes.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class Section(Mapping[str, Any]):
    """A project section that will become a parent task."""

    title: str
    tasks: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        """Return a field using legacy dictionary-style access."""
        if key == "title":
            return self.title
        if key == "tasks":
            return self.tasks
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over field names."""
        return iter(("title", "tasks"))

    def __len__(self) -> int:
        """Return the number of mapping fields."""
        return 2

    def __eq__(self, other: object) -> bool:
        """Compare sections with models or equivalent mappings."""
        if isinstance(other, Section):
            return self.title == other.title and self.tasks == other.tasks
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return NotImplemented

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation."""
        return {"title": self.title, "tasks": list(self.tasks)}


@dataclass(eq=False)
class Project(Mapping[str, Any]):
    """A parsed project name and its sections in source order."""

    project_name: str
    sections: list[Section] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        """Return a field using legacy dictionary-style access."""
        if key == "project_name":
            return self.project_name
        if key == "sections":
            return self.sections
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over field names."""
        return iter(("project_name", "sections"))

    def __len__(self) -> int:
        """Return the number of mapping fields."""
        return 2

    def __eq__(self, other: object) -> bool:
        """Compare projects with models or equivalent mappings."""
        if isinstance(other, Project):
            return (
                self.project_name == other.project_name
                and self.sections == other.sections
            )
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return NotImplemented

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation."""
        return {
            "project_name": self.project_name,
            "sections": [section.to_dict() for section in self.sections],
        }
