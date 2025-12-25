
from __future__ import annotations

import hashlib
from dataclasses import dataclass

@dataclass(frozen=True)
class ContentHash:

    value: str

    HASH_LENGTH: int = 16

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Content hash cannot be empty")
        if len(self.value) != self.HASH_LENGTH:
            raise ValueError(
                f"Content hash must be {self.HASH_LENGTH} characters"
            )

    @classmethod
    def from_content(cls, content: str) -> ContentHash:
        full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(value=full_hash[:cls.HASH_LENGTH])

    @classmethod
    def from_bytes(cls, data: bytes) -> ContentHash:
        full_hash = hashlib.sha256(data).hexdigest()
        return cls(value=full_hash[:cls.HASH_LENGTH])

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ContentHash):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented
