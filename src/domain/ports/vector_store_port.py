
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..value_objects.embedding_vector import EmbeddingVector

@dataclass
class VectorSearchHit:

    id: str
    distance: float
    metadata: Dict[str, Any]

    @property
    def similarity_percent(self) -> float:
        return max(0.0, (1.0 - self.distance / 2.0) * 100.0)

class VectorStorePort(ABC):

    @abstractmethod
    def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
    ) -> bool:
        ...

    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        ...

    @abstractmethod
    def drop_collection(self, name: str) -> bool:
        ...

    @abstractmethod
    def insert(
        self,
        collection: str,
        id: str,
        vector: EmbeddingVector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        ...

    @abstractmethod
    def insert_batch(
        self,
        collection: str,
        ids: List[str],
        vectors: List[EmbeddingVector],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        ...

    @abstractmethod
    def search(
        self,
        collection: str,
        query_vector: EmbeddingVector,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        ...

    @abstractmethod
    def delete(self, collection: str, ids: List[str]) -> int:
        ...

    @abstractmethod
    def get(
        self,
        collection: str,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def count(self, collection: str) -> int:
        ...

    @abstractmethod
    def close(self) -> None:
        ...
