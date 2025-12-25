
import logging
from typing import Any, Dict, List, Optional

from ....domain.ports.vector_store_port import VectorSearchHit
from .base import BaseMilvusStore

logger = logging.getLogger(__name__)


class MilvusServerStore(BaseMilvusStore):

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 19530
    DEFAULT_DB = "default"

    def __init__(
        self,
        uri: Optional[str] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        db_name: str = DEFAULT_DB,
    ) -> None:
        super().__init__()
        self._uri = uri
        self._host = host
        self._port = port
        self._db_name = db_name
        self._client = None
        self._milvus_module: Dict[str, Any] = {}
        self._collection_cache: Dict[str, Any] = {}
        self._initialize_client()

    def _initialize_client(self) -> None:
        try:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                MilvusClient,
                connections,
                utility,
            )

            self._milvus_module = {
                "Collection": Collection,
                "CollectionSchema": CollectionSchema,
                "DataType": DataType,
                "FieldSchema": FieldSchema,
                "MilvusClient": MilvusClient,
                "connections": connections,
                "utility": utility,
            }

            if self._uri:
                self._client = MilvusClient(uri=self._uri)
                logger.info("Milvus connected via URI: %s", self._uri)
            else:
                connections.connect(
                    alias="default",
                    host=self._host,
                    port=str(self._port),
                    db_name=self._db_name,
                )
                self._client = None
                logger.info("Milvus connected to %s:%d", self._host, self._port)

        except ImportError:
            logger.error("pymilvus not installed")
            raise ImportError("pymilvus not installed. Run: pip install pymilvus")

    def _get_collection(self, name: str):
        if name not in self._collection_cache:
            Collection = self._milvus_module["Collection"]
            collection = Collection(name)
            collection.load()
            self._collection_cache[name] = collection
        return self._collection_cache[name]

    def _has_collection(self, name: str) -> bool:
        if self._client is not None:
            return self._client.has_collection(name)
        utility = self._milvus_module["utility"]
        return utility.has_collection(name)

    def _create_collection_internal(
        self,
        name: str,
        dimension: int,
        metric_type: str,
    ) -> bool:
        if self._client is not None:
            self._client.create_collection(
                collection_name=name,
                dimension=dimension,
                metric_type=metric_type,
                auto_id=False,
                id_type="string",
                max_length=512,
            )
        else:
            FieldSchema = self._milvus_module["FieldSchema"]
            CollectionSchema = self._milvus_module["CollectionSchema"]
            DataType = self._milvus_module["DataType"]
            Collection = self._milvus_module["Collection"]

            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    is_primary=True,
                    max_length=512,
                ),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dimension,
                ),
                FieldSchema(
                    name="metadata",
                    dtype=DataType.JSON,
                ),
            ]
            schema = CollectionSchema(
                fields=fields,
                description=f"Collection: {name}",
            )

            collection = Collection(name=name, schema=schema)

            index_params = {
                "metric_type": metric_type,
                "index_type": self.DEFAULT_INDEX_TYPE,
                "params": {"nlist": self.DEFAULT_NLIST},
            }
            collection.create_index(field_name="vector", index_params=index_params)
            collection.load()

        return True

    def _drop_collection_internal(self, name: str) -> None:
        if self._client is not None:
            self._client.drop_collection(name)
        else:
            utility = self._milvus_module["utility"]
            if utility.has_collection(name):
                utility.drop_collection(name)
        self._collection_cache.pop(name, None)

    def _insert_internal(
        self,
        collection: str,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]],
    ) -> bool:
        if self._client is not None:
            data = {"id": id, "vector": vector}
            if metadata:
                data.update(metadata)
            self._client.upsert(collection_name=collection, data=[data])
        else:
            coll = self._get_collection(collection)
            entities = [[id], [vector], [metadata or {}]]
            coll.upsert(entities)
        return True

    def _insert_batch_internal(
        self,
        collection: str,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> int:
        if self._client is not None:
            data = []
            for i, (id_, vec) in enumerate(zip(ids, vectors)):
                record = {"id": id_, "vector": vec}
                if metadatas and i < len(metadatas) and metadatas[i]:
                    record.update(metadatas[i])
                data.append(record)
            self._client.upsert(collection_name=collection, data=data)
        else:
            coll = self._get_collection(collection)
            entities = [ids, vectors, metadatas or [{} for _ in ids]]
            coll.upsert(entities)
        return len(ids)

    def _search_internal(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int,
        filter_expr: Optional[str],
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        hits = []

        if self._client is not None:
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

            results = self._client.search(**search_params)

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
        else:
            coll = self._get_collection(collection)
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": self.DEFAULT_NPROBE, "offset": offset},
            }
            results = coll.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["metadata"],
            )

            if results and len(results) > 0:
                for hit in results[0]:
                    distance = 1.0 - hit.score
                    hits.append(
                        VectorSearchHit(
                            id=hit.id,
                            distance=distance,
                            metadata=hit.entity.get("metadata", {}),
                        )
                    )

        return hits

    def _delete_internal(self, collection: str, ids: List[str]) -> int:
        if self._client is not None:
            self._client.delete(collection_name=collection, ids=ids)
        else:
            coll = self._get_collection(collection)
            id_list = ", ".join(f'"{id_}"' for id_ in ids)
            expr = f"id in [{id_list}]"
            coll.delete(expr)
        return len(ids)

    def _get_internal(
        self,
        collection: str,
        ids: List[str],
    ) -> List[Dict[str, Any]]:
        output = []

        if self._client is not None:
            results = self._client.get(
                collection_name=collection,
                ids=ids,
                output_fields=["*"],
            )

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
        else:
            coll = self._get_collection(collection)
            id_list = ", ".join(f'"{id_}"' for id_ in ids)
            expr = f"id in [{id_list}]"

            results = coll.query(
                expr=expr,
                output_fields=["id", "vector", "metadata"],
            )

            for entity in results:
                data = {
                    "id": entity.get("id", ""),
                    "metadata": entity.get("metadata", {}),
                }
                if "vector" in entity:
                    data["embedding"] = entity["vector"]
                output.append(data)

        return output

    def _count_internal(self, collection: str) -> int:
        if self._client is not None:
            stats = self._client.get_collection_stats(collection)
            return stats.get("row_count", 0)
        else:
            coll = self._get_collection(collection)
            return coll.num_entities

    def close(self) -> None:
        try:
            self._collection_cache.clear()
            self._collection_dims.clear()

            if self._client is not None:
                self._client.close()
            else:
                connections = self._milvus_module.get("connections")
                if connections:
                    connections.disconnect("default")

            logger.debug("Milvus Server store closed")

        except Exception as err:
            logger.warning("Error closing Milvus Server connection: %s", err)
