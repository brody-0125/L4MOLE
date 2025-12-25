
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class CompressionType(Enum):

    NONE = "none"
    ZSTD = "zstd"
    GZIP = "gzip"

@dataclass(frozen=True)
class CompressionResult:

    data: bytes
    original_size: int
    compressed_size: int
    compression_type: CompressionType

    @property
    def ratio(self) -> float:
        if self.original_size == 0:
            return 0.0
        return 1.0 - (self.compressed_size / self.original_size)

    @property
    def is_effective(self) -> bool:
        return self.compressed_size < self.original_size

class TextCompressorPort(ABC):

    @property
    @abstractmethod
    def compression_type(self) -> CompressionType:
        ...

    @abstractmethod
    def compress(self, text: str) -> CompressionResult:
        ...

    @abstractmethod
    def decompress(
        self,
        data: bytes,
        compression_type: CompressionType,
    ) -> str:
        ...

    @abstractmethod
    def is_available(self, compression_type: CompressionType) -> bool:
        ...
