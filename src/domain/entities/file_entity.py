
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from ..value_objects.content_hash import ContentHash
from ..value_objects.file_path import FilePath
from ..value_objects.file_type import FileType

class IndexStatus(Enum):

    PENDING = "pending"
    FILENAME_INDEXED = "filename_indexed"
    CONTENT_INDEXED = "content_indexed"
    FAILED = "failed"

@dataclass
class FileEntity:

    id: Optional[int] = None

    path: FilePath = field(default_factory=lambda: FilePath("."))
    file_type: FileType = field(default_factory=lambda: FileType.from_extension(""))

    size: int = 0
    mtime: int = 0
    content_hash: Optional[ContentHash] = None

    status: IndexStatus = IndexStatus.PENDING
    chunk_count: int = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    chunk_ids: List[int] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        path: str,
        size: int = 0,
        mtime: int = 0,
    ) -> FileEntity:
        file_path = FilePath(path)
        return cls(
            path=file_path,
            file_type=FileType.from_path(path),
            size=size,
            mtime=mtime,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    @property
    def filename(self) -> str:
        return self.path.filename

    @property
    def directory(self) -> str:
        return self.path.directory

    @property
    def is_indexable(self) -> bool:
        return self.file_type.is_indexable

    @property
    def is_indexed(self) -> bool:
        return self.status in (
            IndexStatus.FILENAME_INDEXED,
            IndexStatus.CONTENT_INDEXED,
        )

    @property
    def is_content_indexed(self) -> bool:
        return self.status == IndexStatus.CONTENT_INDEXED

    @property
    def is_failed(self) -> bool:
        return self.status == IndexStatus.FAILED

    def has_changed(self, new_mtime: int) -> bool:
        return self.mtime != new_mtime

    def mark_filename_indexed(self) -> None:
        if self.status == IndexStatus.CONTENT_INDEXED:
            return
        self.status = IndexStatus.FILENAME_INDEXED
        self.updated_at = datetime.now()

    def mark_content_indexed(
        self,
        content_hash: ContentHash,
        chunk_count: int,
    ) -> None:
        self.status = IndexStatus.CONTENT_INDEXED
        self.content_hash = content_hash
        self.chunk_count = chunk_count
        self.updated_at = datetime.now()

    def mark_failed(self) -> None:
        self.status = IndexStatus.FAILED
        self.updated_at = datetime.now()

    def reset_for_reindex(self) -> None:
        self.status = IndexStatus.PENDING
        self.content_hash = None
        self.chunk_count = 0
        self.chunk_ids = []
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": str(self.path),
            "filename": self.filename,
            "file_type": str(self.file_type),
            "size": self.size,
            "mtime": self.mtime,
            "content_hash": str(self.content_hash) if self.content_hash else None,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
        }
