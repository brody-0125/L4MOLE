
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ....domain.ports.vector_store_port import VectorSearchHit, VectorStorePort
from ....domain.value_objects.embedding_vector import EmbeddingVector

logger = logging.getLogger(__name__)


class BaseMilvusStore(VectorStorePort, ABC):

    DEFAULT_INDEX_TYPE = "IVF_FLAT"
    DEFAULT_NLIST = 128
    DEFAULT_NPROBE = 16

    def __init__(self) -> None:
        self._collection_dims: Dict[str, int] = {}

    def _get_metric_type(self, metric: str) -> str:
        metric_map = {
            "cosine": "COSINE",
            "l2": "L2",
            "ip": "IP",
            "euclidean": "L2",
        }
        return metric_map.get(metric.lower(), "COSINE")

    @abstractmethod
    def _has_collection(self, name: str) -> bool:
        ...

    @abstractmethod
    def _create_collection_internal(
        self,
        name: str,
        dimension: int,
        metric_type: str,
    ) -> bool:
        ...

    @abstractmethod
    def _insert_internal(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]],
    ) -> bool:
        ...

    @abstractmethod
    def _insert_batch_internal(
        self,
        collection: str,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> int:
        ...

    @abstractmethod
    def _search_internal(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int,
        filter_expr: Optional[str],
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        ...

    @abstractmethod
    def _delete_internal(self, collection: str, ids: List[str]) -> int:
        ...

    @abstractmethod
    def _get_internal(
        self,
        collection: str,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def _count_internal(self, collection: str) -> int:
        ...

    def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
    ) -> bool:
        try:
            metric_type = self._get_metric_type(metric)

            if self._has_collection(name):
                logger.debug("Collection %s already exists", name)
                self._collection_dims[name] = dimension
                return True

            result = self._create_collection_internal(name, dimension, metric_type)
            if result:
                self._collection_dims[name] = dimension
                logger.debug("Created collection: %s (dim=%d)", name, dimension)
            return result

        except Exception as err:
            logger.error("Failed to create collection %s: %s", name, err)
            return False

    def collection_exists(self, name: str) -> bool:
        try:
            return self._has_collection(name)
        except Exception:
            return False

    def drop_collection(self, name: str) -> bool:
        try:
            self._drop_collection_internal(name)
            self._collection_dims.pop(name, None)
            logger.debug("Dropped collection: %s", name)
            return True
        except Exception as err:
            logger.error("Failed to drop collection %s: %s", name, err)
            return False

    @abstractmethod
    def _drop_collection_internal(self, name: str) -> None:
        ...

    def _ensure_collection_exists(self, collection: str, dimension: int) -> bool:
        try:
            if not self._has_collection(collection):
                logger.info("Auto-creating collection: %s", collection)
                self.create_collection(collection, dimension)
            self._collection_dims[collection] = dimension
            return True
        except Exception as err:
            logger.error("Failed to ensure collection %s exists: %s", collection, err)
            return False

    def insert(
        self,
        collection: str,
        id: str,
        vector: EmbeddingVector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            if not self._ensure_collection_exists(collection, len(vector.values)):
                return False
            return self._insert_internal(
                collection, id, list(vector.values), metadata
            )
        except Exception as err:
            logger.error("Failed to insert vector %s: %s", id, err)
            return False

    def insert_batch(
        self,
        collection: str,
        ids: List[str],
        vectors: List[EmbeddingVector],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        if not ids or not vectors:
            return 0

        try:
            dimension = len(vectors[0].values)
            if not self._ensure_collection_exists(collection, dimension):
                return 0

            vector_lists = [list(v.values) for v in vectors]
            count = self._insert_batch_internal(collection, ids, vector_lists, metadatas)
            logger.debug("Inserted %d vectors into %s", count, collection)
            return count

        except Exception as err:
            logger.error("Failed to insert batch: %s", err)
            return 0

    def search(
        self,
        collection: str,
        query_vector: EmbeddingVector,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        try:
            return self._search_internal(
                collection, list(query_vector.values), top_k, filter_expr, offset
            )
        except Exception as err:
            logger.error("Search failed: %s", err)
            return []

    def delete(self, collection: str, ids: List[str]) -> int:
        if not ids:
            return 0
        try:
            count = self._delete_internal(collection, ids)
            logger.debug("Deleted %d vectors from %s", count, collection)
            return count
        except Exception as err:
            logger.error("Failed to delete vectors: %s", err)
            return 0

    def get(
        self,
        collection: str,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not ids:
            return []
        try:
            return self._get_internal(collection, ids)
        except Exception as err:
            logger.error("Failed to get vectors: %s", err)
            return []

    def count(self, collection: str) -> int:
        try:
            return self._count_internal(collection)
        except Exception as err:
            logger.error("Failed to count collection %s: %s", collection, err)
            return 0
