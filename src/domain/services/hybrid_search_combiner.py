
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..value_objects.search_config import SearchConfig

@dataclass
class HybridSearchHit:

    id: str
    file_path: str
    rrf_score: float
    vector_rank: Optional[int] = None
    keyword_rank: Optional[int] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    chunk_index: Optional[int] = None
    snippet: str = ""

class HybridSearchCombiner:

    def __init__(self, config: Optional[SearchConfig] = None) -> None:
        self._config = config or SearchConfig.default()

    @property
    def config(self) -> SearchConfig:
        return self._config

    def combine(
        self,
        vector_results: List[Tuple[str, str, float, Optional[int], str]],
        keyword_results: List[Tuple[str, str, float, Optional[int], str]],
        top_k: int = 20,
        vector_weight: Optional[float] = None,
        keyword_weight: Optional[float] = None,
    ) -> List[HybridSearchHit]:
        v_weight = vector_weight if vector_weight is not None else self._config.vector_weight
        k_weight = keyword_weight if keyword_weight is not None else self._config.keyword_weight
        k = self._config.rrf_k
        doc_info: Dict[str, Dict] = {}

        for rank, (doc_id, file_path, score, chunk_idx, snippet) in enumerate(vector_results, 1):
            key = self._get_key(file_path, chunk_idx)
            if key not in doc_info:
                doc_info[key] = {
                    "id": doc_id,
                    "file_path": file_path,
                    "chunk_index": chunk_idx,
                    "snippet": snippet,
                    "vector_rank": None,
                    "keyword_rank": None,
                    "vector_score": None,
                    "keyword_score": None,
                }
            doc_info[key]["vector_rank"] = rank
            doc_info[key]["vector_score"] = score
            if snippet and not doc_info[key]["snippet"]:
                doc_info[key]["snippet"] = snippet

        for rank, (doc_id, file_path, score, chunk_idx, snippet) in enumerate(keyword_results, 1):
            key = self._get_key(file_path, chunk_idx)
            if key not in doc_info:
                doc_info[key] = {
                    "id": doc_id,
                    "file_path": file_path,
                    "chunk_index": chunk_idx,
                    "snippet": snippet,
                    "vector_rank": None,
                    "keyword_rank": None,
                    "vector_score": None,
                    "keyword_score": None,
                }
            doc_info[key]["keyword_rank"] = rank
            doc_info[key]["keyword_score"] = score
            if snippet:
                doc_info[key]["snippet"] = snippet

        results = []
        for key, info in doc_info.items():
            rrf_score = 0.0

            if info["vector_rank"] is not None:
                rrf_score += v_weight * (1.0 / (k + info["vector_rank"]))

            if info["keyword_rank"] is not None:
                rrf_score += k_weight * (1.0 / (k + info["keyword_rank"]))

            results.append(
                HybridSearchHit(
                    id=info["id"],
                    file_path=info["file_path"],
                    rrf_score=rrf_score,
                    vector_rank=info["vector_rank"],
                    keyword_rank=info["keyword_rank"],
                    vector_score=info["vector_score"],
                    keyword_score=info["keyword_score"],
                    chunk_index=info["chunk_index"],
                    snippet=info["snippet"],
                )
            )

        results.sort(key=lambda x: x.rrf_score, reverse=True)

        return results[:top_k]

    def _get_key(self, file_path: str, chunk_index: Optional[int]) -> str:
        if chunk_index is not None:
            return f"{file_path}:{chunk_index}"
        return file_path

    def combine_with_boost(
        self,
        vector_results: List[Tuple[str, str, float, Optional[int], str]],
        keyword_results: List[Tuple[str, str, float, Optional[int], str]],
        top_k: int = 20,
        exact_match_boost: Optional[float] = None,
    ) -> List[HybridSearchHit]:
        boost = exact_match_boost if exact_match_boost is not None else self._config.exact_match_boost

        results = self.combine(
            vector_results,
            keyword_results,
            top_k=top_k * 2,
        )

        for result in results:
            if result.vector_rank is not None and result.keyword_rank is not None:
                result.rrf_score *= boost

        results.sort(key=lambda x: x.rrf_score, reverse=True)
        return results[:top_k]
