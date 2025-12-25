
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SearchResultTier(Enum):

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    LOW = "low"

@dataclass(frozen=True)
class SearchResult:

    file_path: str
    similarity_score: float
    match_type: str
    chunk_index: Optional[int] = None
    snippet: str = ""

    @property
    def similarity_percent(self) -> float:
        return self.similarity_score

    @property
    def tier(self) -> SearchResultTier:
        pct = self.similarity_score
        if pct >= 90:
            return SearchResultTier.EXCELLENT
        if pct >= 80:
            return SearchResultTier.GOOD
        if pct >= 60:
            return SearchResultTier.FAIR
        return SearchResultTier.LOW

    def matches_threshold(self, min_similarity: float) -> bool:
        return self.similarity_score >= min_similarity

    def to_dict(self) -> dict:
        return {
            "path": self.file_path,
            "similarity": self.similarity_score,
            "match_type": self.match_type,
            "chunk_index": self.chunk_index,
            "snippet": self.snippet,
            "tier": self.tier.value,
        }
