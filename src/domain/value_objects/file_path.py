
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class FilePath:

    path: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("File path cannot be empty")

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def directory(self) -> str:
        return os.path.dirname(self.path)

    @property
    def extension(self) -> str:
        _, ext = os.path.splitext(self.path)
        return ext.lower().lstrip(".")

    @property
    def absolute(self) -> str:
        return os.path.abspath(self.path)

    def is_hidden(self) -> bool:
        path = os.path.abspath(self.path)

        while path and path != os.path.dirname(path):
            basename = os.path.basename(path)
            if not basename:
                path = os.path.dirname(path)
                continue

            if basename.startswith("."):
                return True

            path = os.path.dirname(path)

        return False

    def is_under(self, directory: str) -> bool:
        abs_path = os.path.abspath(self.path)
        abs_dir = os.path.abspath(directory)
        return abs_path.startswith(abs_dir + os.sep) or abs_path == abs_dir

    def relative_to(self, base: str) -> Optional[str]:
        if not self.is_under(base):
            return None
        return os.path.relpath(self.path, base)

    def with_suffix(self, suffix: str) -> FilePath:
        base, _ = os.path.splitext(self.path)
        new_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        return FilePath(base + new_suffix)

    def __str__(self) -> str:
        return self.path

    def __hash__(self) -> int:
        return hash(self.absolute)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FilePath):
            return NotImplemented
        return self.absolute == other.absolute
