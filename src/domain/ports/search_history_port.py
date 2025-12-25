
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ..value_objects.search_query import SearchMode

@dataclass
class SearchHistoryEntry:

    id: Optional[int]
    query: str
    mode: SearchMode
    result_count: int
    searched_at: datetime

class SearchHistoryPort(ABC):

    @abstractmethod
    def add(
        self,
        query: str,
        mode: SearchMode,
        result_count: int,
    ) -> SearchHistoryEntry:
        ...

    @abstractmethod
    def get_recent(self, limit: int = 50) -> List[SearchHistoryEntry]:
        ...

    @abstractmethod
    def clear(self) -> int:
        ...

    @abstractmethod
    def find_by_query(self, query: str) -> List[SearchHistoryEntry]:
        ...
