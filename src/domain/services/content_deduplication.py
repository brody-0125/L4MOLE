
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..entities.chunk_entity import ChunkEntity
from ..ports.chunk_repository import ChunkRepository
from ..value_objects.content_hash import ContentHash

logger = logging.getLogger(__name__)

@dataclass
class DeduplicationResult:

    new_chunks: List[Tuple[int, str, ContentHash]]

    deduplicated_chunks: List[Tuple[int, ChunkEntity]]

    @property
    def total_chunks(self) -> int:
        return len(self.new_chunks) + len(self.deduplicated_chunks)

    @property
    def dedup_count(self) -> int:
        return len(self.deduplicated_chunks)

    @property
    def dedup_ratio(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.dedup_count / self.total_chunks

    @property
    def embeddings_saved(self) -> int:
        return self.dedup_count

@dataclass
class DeduplicationStats:

    total_chunks_processed: int = 0
    duplicates_found: int = 0
    embeddings_saved: int = 0
    bytes_saved: int = 0

    @property
    def dedup_ratio(self) -> float:
        if self.total_chunks_processed == 0:
            return 0.0
        return self.duplicates_found / self.total_chunks_processed

class ContentDeduplicationService:

    def __init__(
        self,
        chunk_repository: ChunkRepository,
        enabled: bool = True,
    ) -> None:
        self._chunk_repo = chunk_repository
        self._enabled = enabled
        self._stats = DeduplicationStats()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def stats(self) -> DeduplicationStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = DeduplicationStats()

    def analyze_chunks(
        self,
        chunk_texts: List[str],
    ) -> DeduplicationResult:
        if not self._enabled or not chunk_texts:
            return DeduplicationResult(
                new_chunks=[
                    (i, text, ContentHash.from_content(text))
                    for i, text in enumerate(chunk_texts)
                ],
                deduplicated_chunks=[],
            )

        new_chunks: List[Tuple[int, str, ContentHash]] = []
        deduplicated_chunks: List[Tuple[int, ChunkEntity]] = []

        hash_cache: Dict[str, Optional[ChunkEntity]] = {}

        for idx, text in enumerate(chunk_texts):
            content_hash = ContentHash.from_content(text)
            hash_value = content_hash.value

            if hash_value in hash_cache:
                existing = hash_cache[hash_value]
                if existing is not None:
                    deduplicated_chunks.append((idx, existing))
                    self._stats.duplicates_found += 1
                    self._stats.embeddings_saved += 1
                    logger.debug(
                        "Batch-level dedup: chunk %d matches hash %s",
                        idx,
                        hash_value,
                    )
                else:
                    new_chunks.append((idx, text, content_hash))
                continue

            existing = self._chunk_repo.find_by_hash(content_hash)
            hash_cache[hash_value] = existing

            if existing is not None:
                deduplicated_chunks.append((idx, existing))
                self._stats.duplicates_found += 1
                self._stats.embeddings_saved += 1
                if existing.original_size > 0:
                    self._stats.bytes_saved += existing.original_size
                logger.debug(
                    "Repository dedup: chunk %d matches existing chunk %s",
                    idx,
                    existing.vector_id,
                )
            else:
                new_chunks.append((idx, text, content_hash))

        self._stats.total_chunks_processed += len(chunk_texts)

        if deduplicated_chunks:
            logger.info(
                "Deduplication: %d/%d chunks reusing existing vectors (%.1f%% saved)",
                len(deduplicated_chunks),
                len(chunk_texts),
                len(deduplicated_chunks) / len(chunk_texts) * 100,
            )

        return DeduplicationResult(
            new_chunks=new_chunks,
            deduplicated_chunks=deduplicated_chunks,
        )

    def find_existing_chunk(self, content: str) -> Optional[ChunkEntity]:
        if not self._enabled:
            return None

        content_hash = ContentHash.from_content(content)
        return self._chunk_repo.find_by_hash(content_hash)
