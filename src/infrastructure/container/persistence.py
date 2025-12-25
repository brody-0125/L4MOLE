
import logging
from typing import Optional

from ...domain.ports.chunk_repository import ChunkRepository
from ...domain.ports.file_repository import FileRepository
from ...domain.ports.folder_repository import FolderRepository
from ...domain.ports.keyword_search_port import KeywordSearchPort
from ...domain.ports.search_history_port import SearchHistoryPort
from ..persistence.sqlite import (
    SqliteChunkRepository,
    SqliteConnectionManager,
    SqliteFileRepository,
    SqliteFolderRepository,
    SqliteSearchHistoryAdapter,
)
from ..persistence.sqlite.fts_search_adapter import SqliteFTS5Adapter
from .config import PersistenceConfig

logger = logging.getLogger(__name__)

class PersistenceContainer:

    def __init__(self, config: Optional[PersistenceConfig] = None) -> None:
        self._config = config or PersistenceConfig()

        self._connection_manager: Optional[SqliteConnectionManager] = None
        self._file_repo: Optional[FileRepository] = None
        self._chunk_repo: Optional[ChunkRepository] = None
        self._folder_repo: Optional[FolderRepository] = None
        self._search_history: Optional[SearchHistoryPort] = None
        self._keyword_search: Optional[KeywordSearchPort] = None

    @property
    def connection_manager(self) -> SqliteConnectionManager:
        if self._connection_manager is None:
            self._connection_manager = SqliteConnectionManager(
                db_path=self._config.db_path
            )
            logger.debug("Initialized SQLite connection manager")
        return self._connection_manager

    @property
    def file_repository(self) -> FileRepository:
        if self._file_repo is None:
            self._file_repo = SqliteFileRepository(self.connection_manager)
            logger.debug("Initialized file repository")
        return self._file_repo

    @property
    def chunk_repository(self) -> ChunkRepository:
        if self._chunk_repo is None:
            self._chunk_repo = SqliteChunkRepository(self.connection_manager)
            logger.debug("Initialized chunk repository")
        return self._chunk_repo

    @property
    def folder_repository(self) -> FolderRepository:
        if self._folder_repo is None:
            self._folder_repo = SqliteFolderRepository(self.connection_manager)
            logger.debug("Initialized folder repository")
        return self._folder_repo

    @property
    def search_history(self) -> SearchHistoryPort:
        if self._search_history is None:
            self._search_history = SqliteSearchHistoryAdapter(
                self.connection_manager
            )
            logger.debug("Initialized search history adapter")
        return self._search_history

    @property
    def keyword_search(self) -> KeywordSearchPort:
        if self._keyword_search is None:
            self._keyword_search = SqliteFTS5Adapter(self.connection_manager)
            logger.debug("Initialized FTS5 keyword search adapter")
        return self._keyword_search

    def close(self) -> None:
        if self._connection_manager is not None:
            self._connection_manager.close()
            logger.debug("Persistence container closed")
