
from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities.folder_entity import FolderEntity

class FolderRepository(ABC):

    @abstractmethod
    def save(self, entity: FolderEntity) -> FolderEntity:
        ...

    @abstractmethod
    def find_by_id(self, folder_id: int) -> Optional[FolderEntity]:
        ...

    @abstractmethod
    def find_by_path(self, path: str) -> Optional[FolderEntity]:
        ...

    @abstractmethod
    def find_all(self) -> List[FolderEntity]:
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        ...
