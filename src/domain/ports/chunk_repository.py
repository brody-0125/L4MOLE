
from abc import ABC, abstractmethod
from typing import List, Optional

from ..entities.chunk_entity import ChunkEntity
from ..value_objects.content_hash import ContentHash

class ChunkRepository(ABC):

    @abstractmethod
    def save(self, entity: ChunkEntity) -> ChunkEntity:
        ...

    @abstractmethod
    def save_batch(self, entities: List[ChunkEntity]) -> List[ChunkEntity]:
        ...

    @abstractmethod
    def find_by_id(self, chunk_id: int) -> Optional[ChunkEntity]:
        ...

    @abstractmethod
    def find_by_file_id(self, file_id: int) -> List[ChunkEntity]:
        ...

    @abstractmethod
    def find_by_hash(self, content_hash: ContentHash) -> Optional[ChunkEntity]:
        ...

    @abstractmethod
    def find_by_vector_id(self, vector_id: str) -> Optional[ChunkEntity]:
        ...

    @abstractmethod
    def delete_by_file_id(self, file_id: int) -> int:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def get_compression_stats(self) -> dict:
        ...

    @abstractmethod
    def get_vector_ids_for_file(self, file_id: int) -> List[str]:
        ...

    @abstractmethod
    def delete_by_vector_ids(self, vector_ids: List[str]) -> int:
        ...

    @abstractmethod
    def count_by_file_id(self, file_id: int) -> int:
        ...
