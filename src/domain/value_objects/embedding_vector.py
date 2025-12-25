
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

@dataclass(frozen=True)
class EmbeddingVector:

    values: Tuple[float, ...]
    dimension: int

    def __init__(self, values: List[float]) -> None:
        if not values:
            raise ValueError("Embedding vector cannot be empty")

        object.__setattr__(self, "values", tuple(values))
        object.__setattr__(self, "dimension", len(values))

    def to_list(self) -> List[float]:
        return list(self.values)

    def cosine_distance(self, other: EmbeddingVector) -> float:
        if self.dimension != other.dimension:
            raise ValueError(
                f"Dimension mismatch: {self.dimension} vs {other.dimension}"
            )

        dot_product = sum(a * b for a, b in zip(self.values, other.values))
        norm_a = sum(a * a for a in self.values) ** 0.5
        norm_b = sum(b * b for b in other.values) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 1.0

        similarity = dot_product / (norm_a * norm_b)
        return 1.0 - similarity

    def similarity_percent(self, other: EmbeddingVector) -> float:
        distance = self.cosine_distance(other)
        return max(0.0, (1.0 - distance / 2.0) * 100.0)

    def __len__(self) -> int:
        return self.dimension

    def __getitem__(self, index: int) -> float:
        return self.values[index]
