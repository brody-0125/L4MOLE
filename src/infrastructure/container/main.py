
import logging
from typing import Optional

from ...application.use_cases import (
    IndexFileUseCase,
    IndexFolderUseCase,
    SearchUseCase,
)
from ...domain.value_objects.search_config import (
    SearchConfig as DomainSearchConfig,
)
from .config import ContainerConfig
from .indexing import IndexingContainer
from .persistence import PersistenceContainer
from .vector import VectorContainer

logger = logging.getLogger(__name__)

class Container:

    def __init__(self, config: Optional[ContainerConfig] = None) -> None:
        self._config = config or ContainerConfig()

        self._persistence: Optional[PersistenceContainer] = None
        self._vector: Optional[VectorContainer] = None
        self._indexing: Optional[IndexingContainer] = None

        self._search_config: Optional[DomainSearchConfig] = None

        self._index_file_use_case: Optional[IndexFileUseCase] = None
        self._index_folder_use_case: Optional[IndexFolderUseCase] = None
        self._search_use_case: Optional[SearchUseCase] = None

    @property
    def persistence(self) -> PersistenceContainer:
        if self._persistence is None:
            self._persistence = PersistenceContainer(self._config.persistence)
            logger.debug("Initialized persistence container")
        return self._persistence

    @property
    def vector(self) -> VectorContainer:
        if self._vector is None:
            self._vector = VectorContainer(self._config.vector)
            logger.debug("Initialized vector container")
        return self._vector

    @property
    def indexing(self) -> IndexingContainer:
        if self._indexing is None:
            self._indexing = IndexingContainer(
                chunk_repository=self.persistence.chunk_repository,
                config=self._config.indexing,
            )
            logger.debug("Initialized indexing container")
        return self._indexing

    @property
    def connection_manager(self):
        return self.persistence.connection_manager

    @property
    def embedding_service(self):
        return self.vector.embedding_service

    @property
    def compressor(self):
        return self.indexing.compressor

    @property
    def file_reader(self):
        return self.indexing.file_reader

    @property
    def vector_store(self):
        return self.vector.vector_store

    @property
    def file_repository(self):
        return self.persistence.file_repository

    @property
    def chunk_repository(self):
        return self.persistence.chunk_repository

    @property
    def folder_repository(self):
        return self.persistence.folder_repository

    @property
    def search_history(self):
        return self.persistence.search_history

    @property
    def keyword_search(self):
        return self.persistence.keyword_search

    @property
    def deduplication_service(self):
        return self.indexing.deduplication_service

    @property
    def search_config(self) -> DomainSearchConfig:
        if self._search_config is None:
            search_cfg = self._config.search
            self._search_config = DomainSearchConfig(
                rrf_k=search_cfg.rrf_k,
                vector_weight=search_cfg.vector_weight,
                keyword_weight=search_cfg.keyword_weight,
                rrf_score_multiplier=search_cfg.rrf_score_multiplier,
                exact_match_boost=search_cfg.exact_match_boost,
            )
            logger.debug("Initialized search config")
        return self._search_config

    @property
    def index_file_use_case(self) -> IndexFileUseCase:
        if self._index_file_use_case is None:
            self._index_file_use_case = IndexFileUseCase(
                file_repository=self.file_repository,
                chunk_repository=self.chunk_repository,
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
                file_reader=self.file_reader,
                compressor=self.compressor,
                enable_change_detection=self._config.indexing.enable_change_detection,
                keyword_search=self.keyword_search,
                deduplication_service=self.deduplication_service,
            )
            logger.debug("Initialized index file use case")
        return self._index_file_use_case

    @property
    def index_folder_use_case(self) -> IndexFolderUseCase:
        if self._index_folder_use_case is None:
            self._index_folder_use_case = IndexFolderUseCase(
                folder_repository=self.folder_repository,
                file_reader=self.file_reader,
                index_file_use_case=self.index_file_use_case,
            )
            logger.debug("Initialized index folder use case")
        return self._index_folder_use_case

    @property
    def search_use_case(self) -> SearchUseCase:
        if self._search_use_case is None:
            self._search_use_case = SearchUseCase(
                vector_store=self.vector_store,
                embedding_service=self.embedding_service,
                chunk_repository=self.chunk_repository,
                compressor=self.compressor,
                search_history=self.search_history,
                keyword_search=self.keyword_search,
                search_config=self.search_config,
            )
            logger.debug("Initialized search use case")
        return self._search_use_case

    def close(self) -> None:
        if self._vector is not None:
            self._vector.close()

        if self._persistence is not None:
            self._persistence.close()

        logger.info("Container resources closed")

    def __enter__(self) -> "Container":
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        self.close()
        return False

def create_container(
    metadata_db_path: str = "./metadata.db",
    vector_db_path: str = "./milvus_lite.db",
    embedding_model: str = "nomic-embed-text",
    use_compression: bool = True,
) -> Container:
    from ...domain.ports.text_compressor_port import CompressionType
    from .config import (
        IndexingConfig,
        PersistenceConfig,
        VectorConfig,
    )

    config = ContainerConfig(
        persistence=PersistenceConfig(db_path=metadata_db_path),
        vector=VectorConfig(
            db_path=vector_db_path,
            embedding_model=embedding_model,
        ),
        indexing=IndexingConfig(
            compression_type=(
                CompressionType.ZSTD if use_compression else CompressionType.NONE
            ),
        ),
    )

    return Container(config)
