
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..value_objects.file_path import FilePath

@dataclass(frozen=True)
class FolderSettings:

    include_hidden: bool = False
    index_content: bool = True

    def to_dict(self) -> dict:
        return {
            "include_hidden": self.include_hidden,
            "index_content": self.index_content,
        }

@dataclass
class FolderEntity:

    id: Optional[int] = None
    path: FilePath = field(default_factory=lambda: FilePath("."))

    settings: FolderSettings = field(default_factory=FolderSettings)

    file_count: int = 0
    indexed_count: int = 0
    failed_count: int = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_indexed_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        path: str,
        include_hidden: bool = False,
        index_content: bool = True,
    ) -> FolderEntity:
        return cls(
            path=FilePath(path),
            settings=FolderSettings(
                include_hidden=include_hidden,
                index_content=index_content,
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @property
    def include_hidden(self) -> bool:
        return self.settings.include_hidden

    @property
    def index_content(self) -> bool:
        return self.settings.index_content

    @property
    def progress_percent(self) -> float:
        if self.file_count == 0:
            return 0.0
        return (self.indexed_count / self.file_count) * 100.0

    @property
    def is_fully_indexed(self) -> bool:
        return self.indexed_count >= self.file_count and self.file_count > 0

    def update_settings(self, settings: FolderSettings) -> None:
        self.settings = settings
        self.updated_at = datetime.now()

    def update_statistics(
        self,
        file_count: int,
        indexed_count: int,
        failed_count: int = 0,
    ) -> None:
        self.file_count = file_count
        self.indexed_count = indexed_count
        self.failed_count = failed_count
        self.updated_at = datetime.now()

    def mark_indexed(self) -> None:
        self.last_indexed_at = datetime.now()
        self.updated_at = datetime.now()

    def contains(self, file_path: FilePath) -> bool:
        return file_path.is_under(str(self.path))

    def should_include(self, file_path: FilePath) -> bool:
        if not self.contains(file_path):
            return False

        if file_path.is_hidden() and not self.include_hidden:
            return False

        return True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": str(self.path),
            "settings": self.settings.to_dict(),
            "file_count": self.file_count,
            "indexed_count": self.indexed_count,
            "failed_count": self.failed_count,
            "progress_percent": self.progress_percent,
        }
