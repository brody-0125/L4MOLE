
import logging
from typing import Optional

from ...domain.ports.chunk_repository import ChunkRepository
from ...domain.ports.file_reader_port import FileReaderPort
from ...domain.ports.text_compressor_port import TextCompressorPort
from ...domain.services.content_deduplication import ContentDeduplicationService
from ..compression import ZstdTextCompressor
from ..file_system import LocalFileReader
from .config import IndexingConfig

logger = logging.getLogger(__name__)

class IndexingContainer:

    def __init__(
        self,
        chunk_repository: ChunkRepository,
        config: Optional[IndexingConfig] = None,
    ) -> None:
        self._config = config or IndexingConfig()
        self._chunk_repository = chunk_repository

        self._file_reader: Optional[FileReaderPort] = None
        self._compressor: Optional[TextCompressorPort] = None
        self._dedup_service: Optional[ContentDeduplicationService] = None

    @property
    def file_reader(self) -> FileReaderPort:
        if self._file_reader is None:
            self._file_reader = LocalFileReader(
                image_caption_model=self._config.image_caption_model
            )
            logger.debug("Initialized local file reader")
        return self._file_reader

    @property
    def compressor(self) -> TextCompressorPort:
        if self._compressor is None:
            self._compressor = ZstdTextCompressor(
                default_type=self._config.compression_type,
                compression_level=self._config.compression_level,
            )
            logger.debug("Initialized Zstd compressor")
        return self._compressor

    @property
    def deduplication_service(self) -> ContentDeduplicationService:
        if self._dedup_service is None:
            self._dedup_service = ContentDeduplicationService(
                chunk_repository=self._chunk_repository,
                enabled=self._config.enable_deduplication,
            )
            logger.debug(
                "Initialized deduplication service (enabled=%s)",
                self._config.enable_deduplication,
            )
        return self._dedup_service
