
from dataclasses import dataclass

@dataclass(frozen=True)
class SearchConfig:

    rrf_k: int = 60
    """RRF constant. Higher values reduce the impact of top rankings.
    Default of 60 is widely used in IR research (Cormack et al., 2009)."""

    vector_weight: float = 0.5
    """Weight for vector search in hybrid mode (0.0-1.0)."""

    keyword_weight: float = 0.5
    """Weight for keyword/BM25 search in hybrid mode (0.0-1.0)."""

    rrf_score_multiplier: float = 3000.0
    """Multiplier to convert RRF scores (typically < 0.05) to 0-100 range."""

    exact_match_boost: float = 2.0
    """Boost multiplier for documents appearing in both vector and keyword results."""

    def __post_init__(self) -> None:
        if self.rrf_k < 1:
            raise ValueError("rrf_k must be >= 1")
        if not 0.0 <= self.vector_weight <= 1.0:
            raise ValueError("vector_weight must be between 0.0 and 1.0")
        if not 0.0 <= self.keyword_weight <= 1.0:
            raise ValueError("keyword_weight must be between 0.0 and 1.0")
        if self.rrf_score_multiplier <= 0:
            raise ValueError("rrf_score_multiplier must be > 0")
        if self.exact_match_boost < 1.0:
            raise ValueError("exact_match_boost must be >= 1.0")

    @classmethod
    def default(cls) -> "SearchConfig":
        return cls()

    @classmethod
    def vector_biased(cls) -> "SearchConfig":
        return cls(vector_weight=0.7, keyword_weight=0.3)

    @classmethod
    def keyword_biased(cls) -> "SearchConfig":
        return cls(vector_weight=0.3, keyword_weight=0.7)
