
from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from ..value_objects.embedding_vector import EmbeddingVector

class EmbeddingPort(ABC):

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @abstractmethod
    def embed(self, text: str) -> Optional[EmbeddingVector]:
        ...

    @abstractmethod
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Optional[EmbeddingVector]]:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
