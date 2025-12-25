
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet

class FileCategory(Enum):

    TEXT = "text"
    PDF = "pdf"
    IMAGE = "image"
    UNKNOWN = "unknown"

TEXT_EXTENSIONS: FrozenSet[str] = frozenset({
    "txt", "md", "py", "json", "csv", "xml", "yaml", "yml",
    "html", "htm", "css", "js", "ts", "jsx", "tsx",
    "java", "c", "cpp", "h", "hpp", "rs", "go", "rb",
    "sh", "bash", "zsh", "ps1", "bat", "cmd",
    "sql", "ini", "cfg", "conf", "toml",
})

PDF_EXTENSIONS: FrozenSet[str] = frozenset({"pdf"})

IMAGE_EXTENSIONS: FrozenSet[str] = frozenset({
    "png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico", "svg",
})

@dataclass(frozen=True)
class FileType:

    extension: str
    category: FileCategory

    @classmethod
    def from_extension(cls, extension: str) -> FileType:
        ext = extension.lower().lstrip(".")

        if ext in TEXT_EXTENSIONS:
            return cls(extension=ext, category=FileCategory.TEXT)
        if ext in PDF_EXTENSIONS:
            return cls(extension=ext, category=FileCategory.PDF)
        if ext in IMAGE_EXTENSIONS:
            return cls(extension=ext, category=FileCategory.IMAGE)

        return cls(extension=ext, category=FileCategory.UNKNOWN)

    @classmethod
    def from_path(cls, path: str) -> FileType:
        import os
        _, ext = os.path.splitext(path)
        return cls.from_extension(ext)

    @property
    def is_text(self) -> bool:
        return self.category == FileCategory.TEXT

    @property
    def is_pdf(self) -> bool:
        return self.category == FileCategory.PDF

    @property
    def is_image(self) -> bool:
        return self.category == FileCategory.IMAGE

    @property
    def is_indexable(self) -> bool:
        return self.category != FileCategory.UNKNOWN

    def __str__(self) -> str:
        return self.category.value
