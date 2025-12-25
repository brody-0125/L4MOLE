
import pytest

from src.domain.services.hybrid_search_combiner import (
    HybridSearchCombiner,
    HybridSearchHit,
)
from src.domain.value_objects.search_config import SearchConfig

class TestHybridSearchCombiner:

    def test_combine_empty_results(self):
        combiner = HybridSearchCombiner()

        result = combiner.combine([], [], top_k=10)

        assert result == []

    def test_combine_vector_only_results(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/file1.txt", 95.0, 0, "snippet1"),
            ("id2", "/path/file2.txt", 85.0, 1, "snippet2"),
        ]

        result = combiner.combine(vector_results, [], top_k=10)

        assert len(result) == 2
        assert result[0].file_path == "/path/file1.txt"
        assert result[0].vector_rank == 1
        assert result[0].keyword_rank is None
        assert result[1].file_path == "/path/file2.txt"
        assert result[1].vector_rank == 2

    def test_combine_keyword_only_results(self):
        combiner = HybridSearchCombiner()

        keyword_results = [
            ("id1", "/path/file1.txt", 10.5, 0, "match1"),
            ("id2", "/path/file2.txt", 8.2, 1, "match2"),
        ]

        result = combiner.combine([], keyword_results, top_k=10)

        assert len(result) == 2
        assert result[0].file_path == "/path/file1.txt"
        assert result[0].keyword_rank == 1
        assert result[0].vector_rank is None

    def test_combine_overlapping_results(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/common.txt", 95.0, 0, "vector snippet"),
            ("id2", "/path/vector_only.txt", 85.0, 1, "vector only"),
        ]
        keyword_results = [
            ("id1", "/path/common.txt", 10.5, 0, "keyword snippet"),
            ("id3", "/path/keyword_only.txt", 8.2, 1, "keyword only"),
        ]

        result = combiner.combine(vector_results, keyword_results, top_k=10)

        assert result[0].file_path == "/path/common.txt"
        assert result[0].vector_rank == 1
        assert result[0].keyword_rank == 1
        assert result[0].rrf_score > result[1].rrf_score

    def test_combine_with_chunk_index_deduplication(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/file.txt", 95.0, 0, "chunk 0"),
            ("id2", "/path/file.txt", 85.0, 1, "chunk 1"),
        ]

        result = combiner.combine(vector_results, [], top_k=10)

        assert len(result) == 2
        assert result[0].chunk_index == 0
        assert result[1].chunk_index == 1

    def test_combine_respects_top_k(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            (f"id{i}", f"/path/file{i}.txt", 90.0 - i, i, f"snippet{i}")
            for i in range(10)
        ]

        result = combiner.combine(vector_results, [], top_k=5)

        assert len(result) == 5

    def test_combine_weighted_results(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/vector_preferred.txt", 95.0, 0, ""),
            ("id2", "/path/keyword_preferred.txt", 50.0, 0, ""),
        ]
        keyword_results = [
            ("id2", "/path/keyword_preferred.txt", 15.0, 0, ""),
            ("id1", "/path/vector_preferred.txt", 5.0, 0, ""),
        ]

        result_vector_heavy = combiner.combine(
            vector_results, keyword_results,
            top_k=10,
            vector_weight=0.9,
            keyword_weight=0.1,
        )

        result_keyword_heavy = combiner.combine(
            vector_results, keyword_results,
            top_k=10,
            vector_weight=0.1,
            keyword_weight=0.9,
        )

        assert result_vector_heavy[0].file_path == "/path/vector_preferred.txt"
        assert result_keyword_heavy[0].file_path == "/path/keyword_preferred.txt"

    def test_rrf_score_calculation(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/file.txt", 95.0, 0, ""),
        ]

        result = combiner.combine(
            vector_results, [],
            top_k=10,
            vector_weight=1.0,
            keyword_weight=0.5,
        )

        expected_score = 1.0 / 61
        assert abs(result[0].rrf_score - expected_score) < 0.0001

    def test_combine_preserves_snippets(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/file.txt", 95.0, 0, "vector snippet"),
        ]
        keyword_results = [
            ("id1", "/path/file.txt", 10.0, 0, "keyword <mark>match</mark>"),
        ]

        result = combiner.combine(vector_results, keyword_results, top_k=10)

        assert "keyword" in result[0].snippet

    def test_combine_with_boost(self):
        combiner = HybridSearchCombiner()

        vector_results = [
            ("id1", "/path/common.txt", 95.0, 0, ""),
            ("id2", "/path/vector_only.txt", 90.0, 0, ""),
        ]
        keyword_results = [
            ("id3", "/path/keyword_only.txt", 15.0, 0, ""),
            ("id1", "/path/common.txt", 10.0, 0, ""),
        ]

        result = combiner.combine_with_boost(
            vector_results, keyword_results,
            top_k=10,
            exact_match_boost=2.0,
        )

        assert result[0].file_path == "/path/common.txt"
        assert result[0].vector_rank is not None
        assert result[0].keyword_rank is not None

    def test_custom_config(self):
        config = SearchConfig(
            rrf_k=30,
            vector_weight=0.8,
            keyword_weight=0.2,
        )
        combiner = HybridSearchCombiner(config=config)

        assert combiner.config.rrf_k == 30
        assert combiner.config.vector_weight == 0.8
        assert combiner.config.keyword_weight == 0.2

        vector_results = [("id1", "/path/file.txt", 95.0, 0, "")]
        result = combiner.combine(vector_results, [], top_k=10)

        expected_score = 0.8 / 31
        assert abs(result[0].rrf_score - expected_score) < 0.0001

class TestHybridSearchHit:

    def test_create_hit(self):
        hit = HybridSearchHit(
            id="doc1",
            file_path="/path/to/file.txt",
            rrf_score=0.025,
            vector_rank=1,
            keyword_rank=3,
            vector_score=95.0,
            keyword_score=8.5,
            chunk_index=2,
            snippet="matched text",
        )

        assert hit.id == "doc1"
        assert hit.file_path == "/path/to/file.txt"
        assert hit.rrf_score == 0.025
        assert hit.vector_rank == 1
        assert hit.keyword_rank == 3
        assert hit.chunk_index == 2
        assert hit.snippet == "matched text"

    def test_hit_with_defaults(self):
        hit = HybridSearchHit(
            id="doc1",
            file_path="/path/file.txt",
            rrf_score=0.01,
        )

        assert hit.vector_rank is None
        assert hit.keyword_rank is None
        assert hit.chunk_index is None
        assert hit.snippet == ""
