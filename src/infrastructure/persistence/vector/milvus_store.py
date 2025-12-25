
import logging
from typing import Any, Dict, List, Optional

from ....domain.ports.vector_store_port import VectorSearchHit, VectorStorePort
from ....domain.value_objects.embedding_vector import EmbeddingVector

logger = logging.getLogger(__name__)

class MilvusVectorStore(VectorStorePort):

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 19530
    DEFAULT_DB = "default"

    DEFAULT_INDEX_TYPE = "IVF_FLAT"
    DEFAULT_NLIST = 128
    DEFAULT_NPROBE = 16

    def __init__(
        self,
        uri: Optional[str] = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        db_name: str = DEFAULT_DB,
        use_lite: bool = False,
        lite_path: str = "./milvus_lite.db",
    ) -> None:
        self._uri = uri
        self._host = host
        self._port = port
        self._db_name = db_name
        self._use_lite = use_lite
        self._lite_path = lite_path
        self._milvus = None
        self._connections = None
        self._collection_cache: Dict[str, Any] = {}
        self._collection_dims: Dict[str, int] = {}
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

            if self._use_lite:
                self._client = MilvusClient(uri=self._lite_path)
                logger.info("Milvus Lite initialized at %s", self._lite_path)
            elif self._uri:
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
                logger.info(
                    "Milvus connected to %s:%d",
                    self._host,
                    self._port,
                )

        except ImportError:
            logger.error("pymilvus not installed")
            raise ImportError(
                "pymilvus not installed. Run: pip install pymilvus"
            )

    def _get_metric_type(self, metric: str) -> str:
        metric_map = {
            "cosine": "COSINE",
            "l2": "L2",
            "ip": "IP",
            "euclidean": "L2",
        }
        return metric_map.get(metric.lower(), "COSINE")

    def create_collection(
        self,
        name: str,
        dimension: int,
        metric: str = "cosine",
    ) -> bool:
        try:
            metric_type = self._get_metric_type(metric)

            if self._client is not None:
                if self._client.has_collection(name):
                    logger.debug("Collection %s already exists", name)
                    self._collection_dims[name] = dimension
                    return True

                self._client.create_collection(
                    collection_name=name,
                    dimension=dimension,
                    metric_type=metric_type,
                    auto_id=False,
                    id_type="string",
                    max_length=512,
                )
            else:
                utility = self._milvus_module["utility"]
                if utility.has_collection(name):
                    logger.debug("Collection %s already exists", name)
                    self._collection_dims[name] = dimension
                    return True

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

            self._collection_dims[name] = dimension
            logger.debug("Created collection: %s (dim=%d)", name, dimension)
            return True

        except Exception as err:
            logger.error("Failed to create collection %s: %s", name, err)
            return False

    def collection_exists(self, name: str) -> bool:
        try:
            if self._client is not None:
                return self._client.has_collection(name)
            else:
                utility = self._milvus_module["utility"]
                return utility.has_collection(name)
        except Exception:
            return False

    def drop_collection(self, name: str) -> bool:
        try:
            if self._client is not None:
                self._client.drop_collection(name)
            else:
                utility = self._milvus_module["utility"]
                if utility.has_collection(name):
                    utility.drop_collection(name)

            self._collection_cache.pop(name, None)
            self._collection_dims.pop(name, None)
            logger.debug("Dropped collection: %s", name)
            return True

        except Exception as err:
            logger.error("Failed to drop collection %s: %s", name, err)
            return False

    def _get_collection(self, name: str):
        if name not in self._collection_cache:
            Collection = self._milvus_module["Collection"]
            collection = Collection(name)
            collection.load()
            self._collection_cache[name] = collection
        return self._collection_cache[name]

    def _ensure_collection_exists(self, collection: str, dimension: int) -> bool:
        try:
            if self._client is not None:
                if not self._client.has_collection(collection):
                    logger.info("Auto-creating collection: %s", collection)
                    self.create_collection(collection, dimension)
                self._collection_dims[collection] = dimension
                return True
            else:
                utility = self._milvus_module["utility"]
                if not utility.has_collection(collection):
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

            if self._client is not None:
                data = {
                    "id": id,
                    "vector": list(vector.values),
                }
                if metadata:
                    data.update(metadata)

                self._client.upsert(
                    collection_name=collection,
                    data=[data],
                )
            else:
                coll = self._get_collection(collection)
                entities = [
                    [id],
                    [list(vector.values)],
                    [metadata or {}],
                ]
                coll.upsert(entities)

            return True

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

            if self._client is not None:
                data = []
                for i, (id_, vec) in enumerate(zip(ids, vectors)):
                    record = {
                        "id": id_,
                        "vector": list(vec.values),
                    }
                    if metadatas and i < len(metadatas) and metadatas[i]:
                        record.update(metadatas[i])
                    data.append(record)

                self._client.upsert(
                    collection_name=collection,
                    data=data,
                )
            else:
                coll = self._get_collection(collection)
                entities = [
                    ids,
                    [list(v.values) for v in vectors],
                    metadatas or [{} for _ in ids],
                ]
                coll.upsert(entities)

            logger.debug(
                "Inserted %d vectors into %s",
                len(ids),
                collection,
            )
            return len(ids)

        except Exception as err:
            logger.error("Failed to insert batch: %s", err)
            return 0

    def search(
        self,
        collection: str,
        query_vector: EmbeddingVector,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
    ) -> List[VectorSearchHit]:
        try:
            if self._client is not None:
                results = self._client.search(
                    collection_name=collection,
                    data=[list(query_vector.values)],
                    limit=top_k,
                    filter=filter_expr,
                    output_fields=["*"],
                )

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

            else:
                coll = self._get_collection(collection)

                search_params = {
                    "metric_type": "COSINE",
                    "params": {"nprobe": self.DEFAULT_NPROBE},
                }

                results = coll.search(
                    data=[list(query_vector.values)],
                    anns_field="vector",
                    param=search_params,
                    limit=top_k,
                    expr=filter_expr,
                    output_fields=["metadata"],
                )

                hits = []
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

        except Exception as err:
            logger.error("Search failed: %s", err)
            return []

    def delete(self, collection: str, ids: List[str]) -> int:
        if not ids:
            return 0

        try:
            if self._client is not None:
                self._client.delete(
                    collection_name=collection,
                    ids=ids,
                )
            else:
                coll = self._get_collection(collection)
                id_list = ", ".join(f'"{id_}"' for id_ in ids)
                expr = f"id in [{id_list}]"
                coll.delete(expr)

            logger.debug("Deleted %d vectors from %s", len(ids), collection)
            return len(ids)

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
            if self._client is not None:
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

            else:
                coll = self._get_collection(collection)
                id_list = ", ".join(f'"{id_}"' for id_ in ids)
                expr = f"id in [{id_list}]"

                results = coll.query(
                    expr=expr,
                    output_fields=["id", "vector", "metadata"],
                )

                output = []
                for entity in results:
                    data = {
                        "id": entity.get("id", ""),
                        "metadata": entity.get("metadata", {}),
                    }
                    if "vector" in entity:
                        data["embedding"] = entity["vector"]
                    output.append(data)

                return output

        except Exception as err:
            logger.error("Failed to get vectors: %s", err)
            return []

    def count(self, collection: str) -> int:
        try:
            if self._client is not None:
                stats = self._client.get_collection_stats(collection)
                return stats.get("row_count", 0)
            else:
                coll = self._get_collection(collection)
                return coll.num_entities

        except Exception as err:
            logger.error("Failed to count collection %s: %s", collection, err)
            return 0

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

            logger.debug("Milvus store closed")

        except Exception as err:
            logger.warning("Error closing Milvus connection: %s", err)
