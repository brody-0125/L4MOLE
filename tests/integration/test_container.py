
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.application.use_cases import IndexFileUseCase, IndexFolderUseCase, SearchUseCase
from src.domain.entities.chunk_entity import ChunkEntity
from src.domain.entities.file_entity import FileEntity, IndexStatus
from src.domain.entities.folder_entity import FolderEntity
from src.domain.ports.chunk_repository import ChunkRepository
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.file_reader_port import FileContent, FileInfo, FileReaderPort
from src.domain.ports.file_repository import FileRepository
from src.domain.ports.folder_repository import FolderRepository
from src.domain.ports.search_history_port import SearchHistoryEntry, SearchHistoryPort
from src.domain.ports.text_compressor_port import (
    CompressionResult,
    CompressionType,
    TextCompressorPort,
)
from src.domain.ports.vector_store_port import VectorSearchHit, VectorStorePort
from src.domain.value_objects.content_hash import ContentHash
from src.domain.value_objects.embedding_vector import EmbeddingVector
from src.domain.value_objects.file_path import FilePath
from src.domain.value_objects.file_type import FileType
from src.domain.value_objects.search_query import SearchMode

class InMemoryFileRepository(FileRepository):

    def __init__(self):
        self._files: Dict[int, FileEntity] = {}
        self._path_index: Dict[str, int] = {}
        self._next_id = 1

    def save(self, entity: FileEntity) -> FileEntity:
        if entity.id is None:
            entity.id = self._next_id
            self._next_id += 1

        self._files[entity.id] = entity
        self._path_index[entity.path.path] = entity.id
        return entity

    def find_by_id(self, file_id: int) -> Optional[FileEntity]:
        return self._files.get(file_id)

    def find_by_path(self, path: str) -> Optional[FileEntity]:
        file_id = self._path_index.get(path)
        if file_id:
            return self._files.get(file_id)
        return None

    def find_by_directory(self, directory: str) -> List[FileEntity]:
        return [f for f in self._files.values() if f.directory == directory]

    def find_by_status(self, status: IndexStatus, limit: int = 1000) -> List[FileEntity]:
        return [f for f in self._files.values() if f.status == status][:limit]

    def find_changed(self, path: str, mtime: int) -> bool:
        existing = self.find_by_path(path)
        if existing is None:
            return True
        return existing.mtime != mtime

    def delete(self, path: str) -> bool:
        file_id = self._path_index.get(path)
        if file_id:
            del self._files[file_id]
            del self._path_index[path]
            return True
        return False

    def delete_by_id(self, file_id: int) -> bool:
        entity = self._files.get(file_id)
        if entity:
            del self._files[file_id]
            del self._path_index[entity.path.path]
            return True
        return False

    def delete_by_directory(self, directory: str) -> int:
        to_delete = [f for f in self._files.values() if f.directory == directory]
        for f in to_delete:
            self.delete(f.path.path)
        return len(to_delete)

    def count(self) -> int:
        return len(self._files)

    def count_by_status(self, status: IndexStatus) -> int:
        return len([f for f in self._files.values() if f.status == status])

    def exists(self, path: str) -> bool:
        return path in self._path_index

class InMemoryChunkRepository(ChunkRepository):

    def __init__(self):
        self._chunks: Dict[int, ChunkEntity] = {}
        self._file_index: Dict[int, List[int]] = {}
        self._vector_index: Dict[str, int] = {}
        self._next_id = 1

    def save(self, entity: ChunkEntity) -> ChunkEntity:
        if entity.id is None:
            entity.id = self._next_id
            self._next_id += 1

        self._chunks[entity.id] = entity

        if entity.file_id not in self._file_index:
            self._file_index[entity.file_id] = []
        if entity.id not in self._file_index[entity.file_id]:
            self._file_index[entity.file_id].append(entity.id)

        self._vector_index[entity.vector_id] = entity.id
        return entity

    def save_batch(self, entities: List[ChunkEntity]) -> List[ChunkEntity]:
        return [self.save(e) for e in entities]

    def find_by_id(self, chunk_id: int) -> Optional[ChunkEntity]:
        return self._chunks.get(chunk_id)

    def find_by_file_id(self, file_id: int) -> List[ChunkEntity]:
        chunk_ids = self._file_index.get(file_id, [])
        return sorted(
            [self._chunks[cid] for cid in chunk_ids],
            key=lambda c: c.chunk_index,
        )

    def find_by_vector_id(self, vector_id: str) -> Optional[ChunkEntity]:
        chunk_id = self._vector_index.get(vector_id)
        if chunk_id:
            return self._chunks.get(chunk_id)
        return None

    def find_by_hash(self, content_hash: ContentHash) -> Optional[ChunkEntity]:
        for chunk in self._chunks.values():
            if chunk.content_hash.value == content_hash.value:
                return chunk
        return None

    def delete_by_file_id(self, file_id: int) -> int:
        chunk_ids = self._file_index.get(file_id, [])
        for cid in chunk_ids:
            chunk = self._chunks.get(cid)
            if chunk:
                del self._vector_index[chunk.vector_id]
                del self._chunks[cid]
        self._file_index[file_id] = []
        return len(chunk_ids)

    def delete_by_vector_ids(self, vector_ids: List[str]) -> int:
        count = 0
        for vid in vector_ids:
            chunk_id = self._vector_index.get(vid)
            if chunk_id:
                del self._chunks[chunk_id]
                del self._vector_index[vid]
                count += 1
        return count

    def count(self) -> int:
        return len(self._chunks)

    def count_by_file_id(self, file_id: int) -> int:
        return len(self._file_index.get(file_id, []))

    def get_vector_ids_for_file(self, file_id: int) -> List[str]:
        chunks = self.find_by_file_id(file_id)
        return [c.vector_id for c in chunks]

    def get_compression_stats(self) -> dict:
        total_original = sum(c.original_size for c in self._chunks.values())
        total_compressed = sum(c.compressed_size for c in self._chunks.values())
        ratio = 0.0
        if total_original > 0:
            ratio = 1.0 - (total_compressed / total_original)
        return {
            "chunk_count": len(self._chunks),
            "total_original_size": total_original,
            "total_compressed_size": total_compressed,
            "compression_ratio": ratio,
            "space_saved": total_original - total_compressed,
        }

class InMemoryFolderRepository(FolderRepository):

    def __init__(self):
        self._folders: Dict[int, FolderEntity] = {}
        self._path_index: Dict[str, int] = {}
        self._next_id = 1

    def save(self, entity: FolderEntity) -> FolderEntity:
        if entity.id is None:
            entity.id = self._next_id
            self._next_id += 1

        self._folders[entity.id] = entity
        path_str = str(entity.path) if hasattr(entity.path, '__str__') else entity.path
        self._path_index[path_str] = entity.id
        return entity

    def find_by_id(self, folder_id: int) -> Optional[FolderEntity]:
        return self._folders.get(folder_id)

    def find_by_path(self, path: str) -> Optional[FolderEntity]:
        folder_id = self._path_index.get(path)
        if folder_id:
            return self._folders.get(folder_id)
        return None

    def find_all(self) -> List[FolderEntity]:
        return list(self._folders.values())

    def delete(self, path: str) -> bool:
        folder_id = self._path_index.get(path)
        if folder_id:
            del self._folders[folder_id]
            del self._path_index[path]
            return True
        return False

    def exists(self, path: str) -> bool:
        return path in self._path_index

    def count(self) -> int:
        return len(self._folders)

class InMemoryVectorStore(VectorStorePort):

    def __init__(self):
        self._collections: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def create_collection(self, name: str, dimension: int, metric: str = "cosine") -> bool:
        if name not in self._collections:
            self._collections[name] = {}
        return True

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def drop_collection(self, name: str) -> bool:
        if name in self._collections:
            del self._collections[name]
            return True
        return False

    def insert(
        self,
        collection: str,
        id: str,
        vector: EmbeddingVector,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if collection not in self._collections:
            self._collections[collection] = {}

        self._collections[collection][id] = {
            "vector": vector.to_list(),
            "metadata": metadata or {},
        }
        return True

    def insert_batch(
        self,
        collection: str,
        ids: List[str],
        vectors: List[EmbeddingVector],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        if collection not in self._collections:
            self._collections[collection] = {}

        for i, (id_, vector) in enumerate(zip(ids, vectors)):
            meta = metadatas[i] if metadatas else {}
            self._collections[collection][id_] = {
                "vector": vector.to_list(),
                "metadata": meta,
            }
        return len(ids)

    def search(
        self,
        collection: str,
        query_vector: EmbeddingVector,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        offset: int = 0,
    ) -> List[VectorSearchHit]:
        if collection not in self._collections:
            return []

        query = query_vector.to_list()
        results = []

        for id_, data in self._collections[collection].items():
            stored = data["vector"]
            distance = self._cosine_distance(query, stored)
            results.append(
                VectorSearchHit(
                    id=id_,
                    distance=distance,
                    metadata=data["metadata"],
                )
            )

        results.sort(key=lambda x: x.distance)
        return results[offset:offset + top_k]

    def _cosine_distance(self, a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 2.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 2.0

        similarity = dot / (norm_a * norm_b)
        return 1.0 - similarity

    def delete(self, collection: str, ids: List[str]) -> int:
        if collection not in self._collections:
            return 0

        count = 0
        for id_ in ids:
            if id_ in self._collections[collection]:
                del self._collections[collection][id_]
                count += 1
        return count

    def get(self, collection: str, ids: List[str]) -> List[Dict[str, Any]]:
        if collection not in self._collections:
            return []

        return [
            self._collections[collection][id_]
            for id_ in ids
            if id_ in self._collections[collection]
        ]

    def count(self, collection: str) -> int:
        if collection not in self._collections:
            return 0
        return len(self._collections[collection])

    def close(self) -> None:
        pass

class FakeEmbeddingService(EmbeddingPort):

    def __init__(self, dimension: int = 768):
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return "fake-embedding"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> Optional[EmbeddingVector]:
        if not text or not text.strip():
            return None

        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()

        values = []
        for i in range(self._dimension):
            byte_idx = i % len(hash_bytes)
            values.append((hash_bytes[byte_idx] / 255.0) - 0.5)

        return EmbeddingVector(values)

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Optional[EmbeddingVector]]:
        results = []
        for i, text in enumerate(texts):
            results.append(self.embed(text))
            if progress_callback:
                progress_callback(i + 1, len(texts))
        return results

    def is_available(self) -> bool:
        return True

class SimpleTextCompressor(TextCompressorPort):

    @property
    def compression_type(self) -> CompressionType:
        return CompressionType.NONE

    def compress(self, text: str) -> CompressionResult:
        data = text.encode("utf-8")
        return CompressionResult(
            data=data,
            original_size=len(data),
            compressed_size=len(data),
            compression_type=CompressionType.NONE,
        )

    def decompress(self, data: bytes, compression_type: CompressionType) -> str:
        return data.decode("utf-8")

    def is_available(self, compression_type: CompressionType) -> bool:
        return compression_type == CompressionType.NONE

class LocalTestFileReader(FileReaderPort):

    def get_info(self, path: str) -> FileInfo:
        file_exists = os.path.exists(path)
        if file_exists:
            stat = os.stat(path)
            return FileInfo(
                path=FilePath(path),
                size=stat.st_size,
                mtime=int(stat.st_mtime),
                exists=True,
            )
        return FileInfo(
            path=FilePath(path),
            size=0,
            mtime=0,
            exists=False,
        )

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def read_text(self, path: str) -> FileContent:
        return self.read_content(path)

    def read_pdf(self, path: str) -> FileContent:
        return FileContent(
            text="[PDF content placeholder]",
            file_type=FileType.from_extension(".pdf"),
            success=True,
        )

    def describe_image(self, path: str) -> FileContent:
        return FileContent(
            text="[Image description placeholder]",
            file_type=FileType.from_extension(".png"),
            success=True,
        )

    def read_content(self, path: str) -> FileContent:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            return FileContent(
                text=text,
                file_type=FileType.from_path(path),
                success=True,
            )
        except Exception as e:
            return FileContent(
                text="",
                file_type=FileType.from_path(path),
                success=False,
                error=str(e),
            )

    def is_directory(self, path: str) -> bool:
        return os.path.isdir(path)

    def list_files(
        self,
        directory: str,
        recursive: bool = True,
        include_hidden: bool = False,
    ) -> List[FilePath]:
        files = []
        for root, dirs, filenames in os.walk(directory):
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                filenames = [f for f in filenames if not f.startswith(".")]

            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(FilePath(file_path))

            if not recursive:
                break

        return files

class InMemorySearchHistory(SearchHistoryPort):

    def __init__(self):
        self._history: List[SearchHistoryEntry] = []
        self._next_id = 1

    def add(self, query: str, mode: SearchMode, result_count: int) -> SearchHistoryEntry:
        from datetime import datetime

        entry = SearchHistoryEntry(
            id=self._next_id,
            query=query,
            mode=mode,
            result_count=result_count,
            searched_at=datetime.now(),
        )
        self._next_id += 1
        self._history.insert(0, entry)
        return entry

    def get_recent(self, limit: int = 50) -> List[SearchHistoryEntry]:
        return self._history[:limit]

    def clear(self) -> int:
        count = len(self._history)
        self._history = []
        return count

    def find_by_query(self, query: str) -> List[SearchHistoryEntry]:
        return [e for e in self._history if query.lower() in e.query.lower()]

@dataclass
class IntegrationContainerConfig:

    embedding_dimension: int = 768
    use_real_file_system: bool = True

class IntegrationContainer:

    def __init__(self, config: Optional[IntegrationContainerConfig] = None):
        self._config = config or IntegrationContainerConfig()
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

        self._file_repo = InMemoryFileRepository()
        self._chunk_repo = InMemoryChunkRepository()
        self._folder_repo = InMemoryFolderRepository()
        self._vector_store = InMemoryVectorStore()
        self._embedding = FakeEmbeddingService(self._config.embedding_dimension)
        self._compressor = SimpleTextCompressor()
        self._search_history = InMemorySearchHistory()

        if self._config.use_real_file_system:
            self._file_reader = LocalTestFileReader()
        else:
            self._file_reader = LocalTestFileReader()

        self._index_file_use_case: Optional[IndexFileUseCase] = None
        self._index_folder_use_case: Optional[IndexFolderUseCase] = None
        self._search_use_case: Optional[SearchUseCase] = None

    @property
    def file_repository(self) -> FileRepository:
        return self._file_repo

    @property
    def chunk_repository(self) -> ChunkRepository:
        return self._chunk_repo

    @property
    def folder_repository(self) -> FolderRepository:
        return self._folder_repo

    @property
    def vector_store(self) -> VectorStorePort:
        return self._vector_store

    @property
    def embedding_service(self) -> EmbeddingPort:
        return self._embedding

    @property
    def compressor(self) -> TextCompressorPort:
        return self._compressor

    @property
    def file_reader(self) -> FileReaderPort:
        return self._file_reader

    @property
    def search_history(self) -> SearchHistoryPort:
        return self._search_history

    @property
    def index_file_use_case(self) -> IndexFileUseCase:
        if self._index_file_use_case is None:
            self._index_file_use_case = IndexFileUseCase(
                file_repository=self._file_repo,
                chunk_repository=self._chunk_repo,
                vector_store=self._vector_store,
                embedding_service=self._embedding,
                file_reader=self._file_reader,
                compressor=self._compressor,
                enable_change_detection=True,
            )
        return self._index_file_use_case

    @property
    def index_folder_use_case(self) -> IndexFolderUseCase:
        if self._index_folder_use_case is None:
            self._index_folder_use_case = IndexFolderUseCase(
                folder_repository=self._folder_repo,
                file_reader=self._file_reader,
                index_file_use_case=self.index_file_use_case,
            )
        return self._index_folder_use_case

    @property
    def search_use_case(self) -> SearchUseCase:
        if self._search_use_case is None:
            self._search_use_case = SearchUseCase(
                vector_store=self._vector_store,
                embedding_service=self._embedding,
                chunk_repository=self._chunk_repo,
                compressor=self._compressor,
                search_history=self._search_history,
            )
        return self._search_use_case

    def create_temp_dir(self) -> str:
        self._temp_dir = tempfile.TemporaryDirectory()
        return self._temp_dir.name

    def reset(self) -> None:
        self._file_repo = InMemoryFileRepository()
        self._chunk_repo = InMemoryChunkRepository()
        self._folder_repo = InMemoryFolderRepository()
        self._vector_store = InMemoryVectorStore()
        self._search_history = InMemorySearchHistory()

        self._index_file_use_case = None
        self._index_folder_use_case = None
        self._search_use_case = None

    def close(self) -> None:
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def __enter__(self) -> "IntegrationContainer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False
