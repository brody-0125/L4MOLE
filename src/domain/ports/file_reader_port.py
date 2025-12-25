
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from ..value_objects.file_path import FilePath
from ..value_objects.file_type import FileType

@dataclass
class FileInfo:

    path: FilePath
    size: int
    mtime: int
    exists: bool

@dataclass
class FileContent:

    text: str
    file_type: FileType
    success: bool
    error: Optional[str] = None

class FileReaderPort(ABC):

    @abstractmethod
    def get_info(self, path: str) -> FileInfo:
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    def read_text(self, path: str) -> FileContent:
        ...

    @abstractmethod
    def read_pdf(self, path: str) -> FileContent:
        ...

    @abstractmethod
    def describe_image(self, path: str) -> FileContent:
        ...

    @abstractmethod
    def read_content(self, path: str) -> FileContent:
        ...

    @abstractmethod
    def list_files(
        self,
        directory: str,
        recursive: bool = True,
        include_hidden: bool = False,
    ) -> List[FilePath]:
        ...

    @abstractmethod
    def is_directory(self, path: str) -> bool:
        ...
