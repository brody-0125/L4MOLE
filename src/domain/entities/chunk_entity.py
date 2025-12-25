
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..value_objects.content_hash import ContentHash

@dataclass
class ChunkEntity:

    id: Optional[int] = None
    file_id: int = 0
    chunk_index: int = 0

    vector_id: str = ""

    content_hash: Optional[ContentHash] = None
    compressed_content: Optional[bytes] = None

    original_size: int = 0
    compressed_size: int = 0
    compression_type: str = "none"

    created_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        file_id: int,
        chunk_index: int,
        vector_id: str,
        content: str,
        compressed_content: Optional[bytes] = None,
        compression_type: str = "none",
    ) -> ChunkEntity:
        content_hash = ContentHash.from_content(content)
        original_size = len(content.encode("utf-8"))
        compressed_size = (
            len(compressed_content) if compressed_content else original_size
        )

        return cls(
            file_id=file_id,
            chunk_index=chunk_index,
            vector_id=vector_id,
            content_hash=content_hash,
            compressed_content=compressed_content,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_type=compression_type,
            created_at=datetime.now(),
        )

    @property
    def is_compressed(self) -> bool:
        return self.compression_type != "none"

    @property
    def compression_ratio(self) -> float:
        if self.original_size == 0:
            return 0.0
        return 1.0 - (self.compressed_size / self.original_size)

    @property
    def is_duplicate(self) -> bool:
        return self.compressed_content is None and self.original_size == 0

    def matches_hash(self, other_hash: ContentHash) -> bool:
        if self.content_hash is None:
            return False
        return self.content_hash == other_hash

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_id": self.file_id,
            "chunk_index": self.chunk_index,
            "vector_id": self.vector_id,
            "content_hash": str(self.content_hash) if self.content_hash else None,
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_type": self.compression_type,
            "compression_ratio": f"{self.compression_ratio:.1%}",
        }
