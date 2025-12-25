
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ...domain.ports.chunk_repository import ChunkRepository
from ...domain.ports.embedding_port import EmbeddingPort
from ...domain.ports.keyword_search_port import KeywordSearchPort
from ...domain.ports.search_history_port import SearchHistoryPort
from ...domain.ports.text_compressor_port import TextCompressorPort
from ...domain.ports.vector_store_port import VectorStorePort
from ...domain.constants import CONTENT_COLLECTION, FILENAME_COLLECTION
from ...domain.services.hybrid_search_combiner import HybridSearchCombiner
from ...domain.value_objects.embedding_vector import EmbeddingVector
from ...domain.value_objects.search_config import SearchConfig
from ...domain.value_objects.search_query import SearchMode
from ...domain.value_objects.search_result import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class SearchResponse:

    query: str
    mode: SearchMode
    results: List[SearchResult]
    total_count: int
    offset: int = 0
    has_more: bool = False

    @property
    def has_results(self) -> bool:
        return len(self.results) > 0

class SearchUseCase:

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedding_service: EmbeddingPort,
        chunk_repository: ChunkRepository,
        compressor: TextCompressorPort,
        search_history: Optional[SearchHistoryPort] = None,
        keyword_search: Optional[KeywordSearchPort] = None,
        search_config: Optional[SearchConfig] = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedding = embedding_service
        self._chunk_repo = chunk_repository
        self._compressor = compressor
        self._search_history = search_history
        self._keyword_search = keyword_search
        self._search_config = search_config or SearchConfig.default()
        self._hybrid_combiner = HybridSearchCombiner(config=self._search_config)

    def execute(
        self,
        query: str,
        mode: SearchMode = SearchMode.COMBINED,
        top_k: int = 20,
        include_content: bool = False,
        offset: int = 0,
    ) -> SearchResponse:
        if not query or not query.strip():
            raise ValueError("Search query text cannot be empty")

        logger.info(
            "Searching: '%s' (mode=%s, top_k=%d, offset=%d)",
            query, mode.value, top_k, offset,
        )

        query_embedding = self._embedding.embed(query)

        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return SearchResponse(
                query=query,
                mode=mode,
                results=[],
                total_count=0,
                offset=offset,
                has_more=False,
            )

        results: List[SearchResult] = []
        fetch_count = top_k + 1

        if mode == SearchMode.FILENAME:
            results = self._search_filenames(query_embedding, fetch_count, offset)

        elif mode == SearchMode.CONTENT:
            results = self._search_content(
                query_embedding,
                fetch_count,
                include_content,
                offset,
            )

        elif mode == SearchMode.HYBRID:
            results = self._search_hybrid(
                query,
                query_embedding,
                fetch_count,
                include_content,
                offset,
            )

        else:
            filename_results = self._search_filenames(
                query_embedding,
                fetch_count // 2,
                offset // 2,
            )
            content_results = self._search_content(
                query_embedding,
                fetch_count // 2,
                include_content,
                offset // 2,
            )
            results = self._merge_results(
                filename_results,
                content_results,
                fetch_count,
            )

        has_more = len(results) > top_k
        if has_more:
            results = results[:top_k]

        if self._search_history and offset == 0:
            self._search_history.add(
                query=query,
                mode=mode,
                result_count=len(results),
            )

        logger.info("Found %d results for '%s' (has_more=%s)", len(results), query, has_more)

        return SearchResponse(
            query=query,
            mode=mode,
            results=results,
            total_count=len(results),
            offset=offset,
            has_more=has_more,
        )

    def _search_filenames(
        self,
        query_embedding,
        top_k: int,
        offset: int = 0,
    ) -> List[SearchResult]:
        hits = self._vector_store.search(
            collection=FILENAME_COLLECTION,
            query_vector=query_embedding,
            top_k=top_k,
            offset=offset,
        )

        results = []
        for hit in hits:
            results.append(
                SearchResult(
                    file_path=hit.metadata.get("path", hit.id),
                    similarity_score=hit.similarity_percent,
                    match_type="filename",
                    chunk_index=None,
                    snippet=hit.metadata.get("filename", ""),
                )
            )

        return results

    def _search_content(
        self,
        query_embedding,
        top_k: int,
        include_content: bool = False,
        offset: int = 0,
    ) -> List[SearchResult]:
        hits = self._vector_store.search(
            collection=CONTENT_COLLECTION,
            query_vector=query_embedding,
            top_k=top_k,
            offset=offset,
        )

        results = []
        for hit in hits:
            snippet = ""

            if include_content:
                chunk = self._chunk_repo.find_by_vector_id(hit.id)
                if chunk and chunk.compressed_content:
                    try:
                        snippet = self._compressor.decompress(
                            chunk.compressed_content,
                            chunk.compression_type,
                        )
                        if len(snippet) > 500:
                            snippet = snippet[:500] + "..."
                    except Exception as err:
                        logger.warning("Failed to decompress chunk: %s", err)

            results.append(
                SearchResult(
                    file_path=hit.metadata.get("path", ""),
                    similarity_score=hit.similarity_percent,
                    match_type="content",
                    chunk_index=hit.metadata.get("chunk_index"),
                    snippet=snippet,
                )
            )

        return results

    def _merge_results(
        self,
        filename_results: List[SearchResult],
        content_results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        seen_paths = set()
        merged = []

        all_results = filename_results + content_results

        all_results.sort(key=lambda r: r.similarity_score, reverse=True)

        for result in all_results:
            if result.match_type == "content":
                if result.file_path in seen_paths:
                    continue
                seen_paths.add(result.file_path)

            merged.append(result)

            if len(merged) >= top_k:
                break

        return merged

    def _search_hybrid(
        self,
        query: str,
        query_embedding,
        top_k: int,
        include_content: bool = False,
        offset: int = 0,
    ) -> List[SearchResult]:
        if self._keyword_search is None:
            logger.warning("Hybrid search requested but no keyword search available, falling back to vector search")
            return self._search_content(query_embedding, top_k, include_content, offset)

        vector_hits = self._vector_store.search(
            collection=CONTENT_COLLECTION,
            query_vector=query_embedding,
            top_k=top_k,
            offset=offset,
        )

        vector_results: List[Tuple[str, str, float, Optional[int], str]] = []
        for hit in vector_hits:
            snippet = ""
            if include_content:
                chunk = self._chunk_repo.find_by_vector_id(hit.id)
                if chunk and chunk.compressed_content:
                    try:
                        snippet = self._compressor.decompress(
                            chunk.compressed_content,
                            chunk.compression_type,
                        )
                        if len(snippet) > 500:
                            snippet = snippet[:500] + "..."
                    except Exception as err:
                        logger.warning("Failed to decompress chunk: %s", err)

            vector_results.append((
                hit.id,
                hit.metadata.get("path", ""),
                hit.similarity_percent,
                hit.metadata.get("chunk_index"),
                snippet,
            ))

        keyword_hits = self._keyword_search.search(query, top_k=top_k, offset=offset)

        keyword_results: List[Tuple[str, str, float, Optional[int], str]] = []
        for hit in keyword_hits:
            keyword_results.append((
                hit.id,
                hit.file_path,
                hit.score,
                hit.chunk_index,
                hit.snippet,
            ))

        hybrid_hits = self._hybrid_combiner.combine(
            vector_results=vector_results,
            keyword_results=keyword_results,
            top_k=top_k,
        )

        results = []
        for hit in hybrid_hits:
            normalized_score = min(100.0, hit.rrf_score * self._search_config.rrf_score_multiplier)

            results.append(
                SearchResult(
                    file_path=hit.file_path,
                    similarity_score=normalized_score,
                    match_type="hybrid",
                    chunk_index=hit.chunk_index,
                    snippet=hit.snippet,
                )
            )

        return results

    def get_search_history(self, limit: int = 50) -> List:
        if self._search_history:
            return self._search_history.get_recent(limit)
        return []

    def clear_search_history(self) -> int:
        if self._search_history:
            return self._search_history.clear()
        return 0
