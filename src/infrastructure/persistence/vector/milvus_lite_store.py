
import logging
import threading
from typing import Any, Dict, List, Optional

from ....domain.ports.vector_store_port import VectorSearchHit
from .base import BaseMilvusStore

logger = logging.getLogger(__name__)


class MilvusLiteStore(BaseMilvusStore):

    def __init__(self, db_path: str = "./milvus_lite.db") -> None:
        super().__init__()
        self._db_path = db_path
        self._client = None
        self._lock = threading.Lock()
        self._initialize_client()

    def _initialize_client(self) -> None:
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self._db_path)
            logger.info("Milvus Lite initialized at %s", self._db_path)

        except ImportError:
            logger.error("pymilvus not installed")
            raise ImportError("pymilvus not installed. Run: pip install pymilvus")

    def _ensure_connected(self) -> None:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._initialize_client()

    def _has_collection(self, name: str) -> bool:
        return self._client.has_collection(name)

    def _create_collection_internal(
        self,
        name: str,
        dimension: int,
        metric_type: str,
    ) -> bool:
        self._client.create_collection(
            collection_name=name,
            dimension=dimension,
            metric_type=metric_type,
            auto_id=False,
            id_type="string",
            max_length=512,
        )
        return True

    def _drop_collection_internal(self, name: str) -> None:
        self._client.drop_collection(name)

    def _insert_internal(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]],
    ) -> bool:
        data = {"id": id, "vector": vector}
        if metadata:
            data.update(metadata)
        self._client.upsert(collection_name=collection, data=[data])
        return True

    def _insert_batch_internal(
        self,
        collection: str,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> int:
        data = []
        for i, (id_, vec) in enumerate(zip(ids, vectors)):
            record = {"id": id_, "vector": vec}
            if metadatas and i < len(metadatas) and metadatas[i]:
                record.update(metadatas[i])
            data.append(record)

        self._client.upsert(collection_name=collection, data=data)
        return len(ids)

    def _search_internal(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int,
        filter_expr: Optional[str],
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        self._ensure_connected()

        search_params = {
            "collection_name": collection,
            "data": [query_vector],
            "limit": top_k,
            "output_fields": ["*"],
        }
        if filter_expr:
            search_params["filter"] = filter_expr
        if offset > 0:
            search_params["offset"] = offset

        try:
            results = self._client.search(**search_params)
        except Exception as err:
            if "connection" in str(err).lower():
                logger.warning("Connection lost, reconnecting: %s", err)
                with self._lock:
                    self._client = None
                    self._initialize_client()
                results = self._client.search(**search_params)
            else:
                raise

        hits = []
        if results and len(results) > 0:
            for hit in results[0]:
                distance = 1.0 - hit.get("distance", 0.0)
                entity = hit.get("entity", {})
                metadata = {
                    k: v for k, v in entity.items()
                    if k not in ("id", "vector")
                }
                hits.append(
                    VectorSearchHit(
                        id=hit.get("id", ""),
                        distance=distance,
                        metadata=metadata,
                    )
                )
        return hits

    def _delete_internal(self, collection: str, ids: List[str]) -> int:
        self._client.delete(collection_name=collection, ids=ids)
        return len(ids)

    def _get_internal(
        self,
        collection: str,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        results = self._client.get(
            collection_name=collection,
            ids=ids,
            output_fields=["*"],
        )

        output = []
        for entity in results:
            data = {
                "id": entity.get("id", ""),
                "metadata": {
                    k: v for k, v in entity.items()
                    if k not in ("id", "vector")
                },
            }
            if "vector" in entity:
                data["embedding"] = entity["vector"]
            output.append(data)
        return output

    def _count_internal(self, collection: str) -> int:
        stats = self._client.get_collection_stats(collection)
        return stats.get("row_count", 0)

    def close(self) -> None:
        try:
            self._collection_dims.clear()
            if self._client is not None:
                self._client.close()
            logger.debug("Milvus Lite store closed")
        except Exception as err:
            logger.warning("Error closing Milvus Lite connection: %s", err)
