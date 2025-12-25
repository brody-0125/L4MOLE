
import pytest
from unittest.mock import MagicMock

from src.domain.entities.chunk_entity import ChunkEntity
from src.domain.services.content_deduplication import (
    ContentDeduplicationService,
    DeduplicationResult,
    DeduplicationStats,
)
from src.domain.value_objects.content_hash import ContentHash

class TestDeduplicationResult:

    def test_total_chunks(self):
        result = DeduplicationResult(
            new_chunks=[(0, "text1", ContentHash.from_content("text1"))],
            deduplicated_chunks=[(1, MagicMock())],
        )
        assert result.total_chunks == 2

    def test_dedup_ratio(self):
        result = DeduplicationResult(
            new_chunks=[(0, "text1", ContentHash.from_content("text1"))],
            deduplicated_chunks=[(1, MagicMock()), (2, MagicMock())],
        )
        assert abs(result.dedup_ratio - 2/3) < 0.001

    def test_dedup_ratio_empty(self):
        result = DeduplicationResult(new_chunks=[], deduplicated_chunks=[])
        assert result.dedup_ratio == 0.0

    def test_embeddings_saved(self):
        result = DeduplicationResult(
            new_chunks=[],
            deduplicated_chunks=[(0, MagicMock()), (1, MagicMock())],
        )
        assert result.embeddings_saved == 2

class TestDeduplicationStats:

    def test_default_values(self):
        stats = DeduplicationStats()
        assert stats.total_chunks_processed == 0
        assert stats.duplicates_found == 0
        assert stats.embeddings_saved == 0
        assert stats.bytes_saved == 0

    def test_dedup_ratio(self):
        stats = DeduplicationStats(
            total_chunks_processed=10,
            duplicates_found=3,
        )
        assert stats.dedup_ratio == 0.3

class TestContentDeduplicationService:

    def _create_mock_chunk(self, content: str) -> ChunkEntity:
        return ChunkEntity(
            id=1,
            file_id=1,
            chunk_index=0,
            vector_id=f"existing_vector_{content[:8]}",
            content_hash=ContentHash.from_content(content),
            original_size=len(content),
        )

    def test_disabled_service_returns_all_as_new(self):
        mock_repo = MagicMock()
        service = ContentDeduplicationService(mock_repo, enabled=False)

        chunks = ["text1", "text2", "text3"]
        result = service.analyze_chunks(chunks)

        assert len(result.new_chunks) == 3
        assert len(result.deduplicated_chunks) == 0
        mock_repo.find_by_hash.assert_not_called()

    def test_empty_chunks_returns_empty_result(self):
        mock_repo = MagicMock()
        service = ContentDeduplicationService(mock_repo, enabled=True)

        result = service.analyze_chunks([])

        assert len(result.new_chunks) == 0
        assert len(result.deduplicated_chunks) == 0

    def test_no_duplicates_found(self):
        mock_repo = MagicMock()
        mock_repo.find_by_hash.return_value = None
        service = ContentDeduplicationService(mock_repo, enabled=True)

        chunks = ["text1", "text2"]
        result = service.analyze_chunks(chunks)

        assert len(result.new_chunks) == 2
        assert len(result.deduplicated_chunks) == 0
        assert result.new_chunks[0][0] == 0
        assert result.new_chunks[0][1] == "text1"

    def test_duplicate_found_in_repository(self):
        mock_repo = MagicMock()
        existing_chunk = self._create_mock_chunk("duplicate text")

        def find_by_hash(content_hash):
            if content_hash.value == ContentHash.from_content("duplicate text").value:
                return existing_chunk
            return None

        mock_repo.find_by_hash.side_effect = find_by_hash
        service = ContentDeduplicationService(mock_repo, enabled=True)

        chunks = ["new text", "duplicate text"]
        result = service.analyze_chunks(chunks)

        assert len(result.new_chunks) == 1
        assert len(result.deduplicated_chunks) == 1
        assert result.new_chunks[0][1] == "new text"
        assert result.deduplicated_chunks[0][0] == 1
        assert result.deduplicated_chunks[0][1] == existing_chunk

    def test_batch_level_deduplication(self):
        mock_repo = MagicMock()
        mock_repo.find_by_hash.return_value = None
        service = ContentDeduplicationService(mock_repo, enabled=True)

        chunks = ["unique", "repeated", "repeated"]
        result = service.analyze_chunks(chunks)

        assert len(result.new_chunks) == 3
        assert len(result.deduplicated_chunks) == 0

    def test_stats_accumulation(self):
        mock_repo = MagicMock()
        existing_chunk = self._create_mock_chunk("duplicate")
        existing_chunk.original_size = 100

        mock_repo.find_by_hash.return_value = existing_chunk
        service = ContentDeduplicationService(mock_repo, enabled=True)

        service.analyze_chunks(["duplicate"])
        service.analyze_chunks(["duplicate"])

        assert service.stats.total_chunks_processed == 2
        assert service.stats.duplicates_found == 2
        assert service.stats.embeddings_saved == 2
        assert service.stats.bytes_saved == 200

    def test_reset_stats(self):
        mock_repo = MagicMock()
        mock_repo.find_by_hash.return_value = None
        service = ContentDeduplicationService(mock_repo, enabled=True)

        service.analyze_chunks(["text"])
        service.reset_stats()

        assert service.stats.total_chunks_processed == 0

    def test_find_existing_chunk(self):
        mock_repo = MagicMock()
        existing_chunk = self._create_mock_chunk("test content")
        mock_repo.find_by_hash.return_value = existing_chunk

        service = ContentDeduplicationService(mock_repo, enabled=True)
        result = service.find_existing_chunk("test content")

        assert result == existing_chunk

    def test_find_existing_chunk_disabled(self):
        mock_repo = MagicMock()
        service = ContentDeduplicationService(mock_repo, enabled=False)

        result = service.find_existing_chunk("test content")

        assert result is None
        mock_repo.find_by_hash.assert_not_called()
