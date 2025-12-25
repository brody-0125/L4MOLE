
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SearchMode(Enum):

    FILENAME = "filename"
    CONTENT = "content"
    COMBINED = "combined"
    HYBRID = "hybrid"

@dataclass(frozen=True)
class SearchQuery:

    text: str
    mode: SearchMode = SearchMode.FILENAME
    max_results: int = 10
    min_similarity: float = 0.0
    file_type_filter: Optional[str] = None
    directory_filter: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("Search query text cannot be empty")
        if self.max_results < 1:
            raise ValueError("max_results must be at least 1")
        if not 0.0 <= self.min_similarity <= 100.0:
            raise ValueError("min_similarity must be between 0 and 100")

    @property
    def normalized_text(self) -> str:
        return self.text.strip()

    def with_mode(self, mode: SearchMode) -> SearchQuery:
        return SearchQuery(
            text=self.text,
            mode=mode,
            max_results=self.max_results,
            min_similarity=self.min_similarity,
            file_type_filter=self.file_type_filter,
            directory_filter=self.directory_filter,
        )

    def with_max_results(self, max_results: int) -> SearchQuery:
        return SearchQuery(
            text=self.text,
            mode=self.mode,
            max_results=max_results,
            min_similarity=self.min_similarity,
            file_type_filter=self.file_type_filter,
            directory_filter=self.directory_filter,
        )

    def with_filters(
        self,
        file_type: Optional[str] = None,
        directory: Optional[str] = None,
    ) -> SearchQuery:
        return SearchQuery(
            text=self.text,
            mode=self.mode,
            max_results=self.max_results,
            min_similarity=self.min_similarity,
            file_type_filter=file_type or self.file_type_filter,
            directory_filter=directory or self.directory_filter,
        )
