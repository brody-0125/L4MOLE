
from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities.file_entity import FileEntity, IndexStatus

class FileRepository(ABC):

    @abstractmethod
    def save(self, entity: FileEntity) -> FileEntity:
        ...

    @abstractmethod
    def find_by_id(self, file_id: int) -> Optional[FileEntity]:
        ...

    @abstractmethod
    def find_by_path(self, path: str) -> Optional[FileEntity]:
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    def find_by_status(
        self,
        status: IndexStatus,
        limit: int = 1000,
    ) -> List[FileEntity]:
        ...

    @abstractmethod
    def find_by_directory(self, directory: str) -> List[FileEntity]:
        ...

    @abstractmethod
    def find_changed(self, path: str, mtime: int) -> bool:
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        ...

    @abstractmethod
    def delete_by_id(self, file_id: int) -> bool:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def count_by_status(self, status: IndexStatus) -> int:
        ...
