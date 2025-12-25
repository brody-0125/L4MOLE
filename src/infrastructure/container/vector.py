
import logging
from typing import Optional

from ...domain.ports.embedding_port import EmbeddingPort
from ...domain.ports.vector_store_port import VectorStorePort
from ..embedding import OllamaEmbeddingAdapter
from ..persistence.vector import MilvusLiteStore, MilvusServerStore
from .config import VectorConfig, VectorStoreType

logger = logging.getLogger(__name__)


class VectorContainer:

    def __init__(self, config: Optional[VectorConfig] = None) -> None:
        self._config = config or VectorConfig()

        self._vector_store: Optional[VectorStorePort] = None
        self._embedding_service: Optional[EmbeddingPort] = None

    @property
    def vector_store(self) -> VectorStorePort:
        if self._vector_store is None:
            store_type = self._config.store_type

            if store_type == VectorStoreType.MILVUS:
                self._vector_store = MilvusServerStore(
                    uri=self._config.milvus_uri,
                    host=self._config.milvus_host,
                    port=self._config.milvus_port,
                )
                logger.debug("Initialized Milvus Server store")

            elif store_type == VectorStoreType.MILVUS_LITE:
                self._vector_store = MilvusLiteStore(
                    db_path=self._config.db_path,
                )
                logger.debug("Initialized Milvus Lite store")

            else:
                raise ValueError(f"Unknown vector store type: {store_type}")

        return self._vector_store

    @property
    def embedding_service(self) -> EmbeddingPort:
        if self._embedding_service is None:
            self._embedding_service = OllamaEmbeddingAdapter(
                model_name=self._config.embedding_model,
                dimension=self._config.embedding_dimension,
            )
            logger.debug("Initialized Ollama embedding adapter")
        return self._embedding_service

    def close(self) -> None:
        if self._vector_store is not None:
            self._vector_store.close()
            logger.debug("Vector container closed")
