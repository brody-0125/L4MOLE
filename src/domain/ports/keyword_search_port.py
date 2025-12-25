
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class KeywordSearchHit:

    id: str
    score: float
    file_path: str
    chunk_index: Optional[int] = None
    snippet: str = ""

class KeywordSearchPort(ABC):

    @abstractmethod
    def index_content(
        self,
        doc_id: str,
        content: str,
        file_path: str,
        chunk_index: Optional[int] = None,
    ) -> bool:
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 20,
        offset: int = 0,
    ) -> List[KeywordSearchHit]:
        pass

    @abstractmethod
    def delete_by_file_path(self, file_path: str) -> int:
        pass

    @abstractmethod
    def delete_by_doc_id(self, doc_id: str) -> bool:
        pass

    @abstractmethod
    def count(self) -> int:
        pass
