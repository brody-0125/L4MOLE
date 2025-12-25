
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ...domain.ports.text_compressor_port import CompressionType

class VectorStoreType(Enum):

    MILVUS = "milvus"
    MILVUS_LITE = "milvus_lite"

@dataclass
class PersistenceConfig:

    db_path: str = "./metadata.db"

@dataclass
class VectorConfig:

    store_type: VectorStoreType = VectorStoreType.MILVUS_LITE
    db_path: str = "./milvus_lite.db"
    milvus_uri: Optional[str] = None
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

@dataclass
class IndexingConfig:

    compression_type: CompressionType = CompressionType.ZSTD
    compression_level: int = 3

    image_caption_model: str = "llava"

    enable_change_detection: bool = True
    enable_deduplication: bool = True

@dataclass
class SearchConfig:

    rrf_k: int = 60
    vector_weight: float = 0.5
    keyword_weight: float = 0.5
    rrf_score_multiplier: float = 3000.0
    exact_match_boost: float = 2.0

@dataclass
class ContainerConfig:

    persistence: PersistenceConfig = None
    vector: VectorConfig = None
    indexing: IndexingConfig = None
    search: SearchConfig = None

    def __post_init__(self) -> None:
        if self.persistence is None:
            self.persistence = PersistenceConfig()
        if self.vector is None:
            self.vector = VectorConfig()
        if self.indexing is None:
            self.indexing = IndexingConfig()
        if self.search is None:
            self.search = SearchConfig()

    @classmethod
    def default(cls) -> "ContainerConfig":
        return cls()

    @classmethod
    def from_paths(
        cls,
        metadata_db_path: str = "./metadata.db",
        vector_db_path: str = "./milvus_lite.db",
    ) -> "ContainerConfig":
        return cls(
            persistence=PersistenceConfig(db_path=metadata_db_path),
            vector=VectorConfig(db_path=vector_db_path),
        )
