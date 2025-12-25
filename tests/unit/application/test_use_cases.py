
from unittest.mock import MagicMock, Mock, patch
from typing import List, Optional

import pytest

from src.application.use_cases.index_file import IndexFileUseCase, IndexFileResult
from src.application.use_cases.index_folder import IndexFolderUseCase, IndexFolderResult
from src.application.use_cases.search import SearchUseCase, SearchResponse
from src.domain.entities.file_entity import FileEntity, IndexStatus
from src.domain.entities.chunk_entity import ChunkEntity
from src.domain.entities.folder_entity import FolderEntity
from src.domain.ports.chunk_repository import ChunkRepository
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.file_reader_port import FileReaderPort, FileInfo, FileContent
from src.domain.ports.file_repository import FileRepository
from src.domain.ports.folder_repository import FolderRepository
from src.domain.ports.text_compressor_port import (
    TextCompressorPort,
    CompressionResult,
    CompressionType,
)
from src.domain.ports.vector_store_port import VectorStorePort, VectorSearchHit
from src.domain.ports.search_history_port import SearchHistoryPort
from src.domain.value_objects.content_hash import ContentHash
from src.domain.value_objects.embedding_vector import EmbeddingVector
from src.domain.value_objects.file_path import FilePath
from src.domain.value_objects.file_type import FileType
from src.domain.value_objects.search_query import SearchMode

class TestIndexFileUseCase:

    @pytest.fixture
    def mock_file_repo(self) -> MagicMock:
        mock = MagicMock(spec=FileRepository)
        mock.find_by_path.return_value = None
        mock.save.side_effect = lambda e: setattr(e, "id", 1) or e
        return mock

    @pytest.fixture
    def mock_chunk_repo(self) -> MagicMock:
        mock = MagicMock(spec=ChunkRepository)
        mock.get_vector_ids_for_file.return_value = []
        mock.save_batch.side_effect = lambda entities: entities
        return mock

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        mock = MagicMock(spec=VectorStorePort)
        mock.insert.return_value = True
        mock.insert_batch.return_value = 1
        return mock

    @pytest.fixture
    def mock_embedding(self) -> MagicMock:
        mock = MagicMock(spec=EmbeddingPort)
        mock.embed.return_value = EmbeddingVector([0.1] * 768)
        return mock

    @pytest.fixture
    def mock_file_reader(self) -> MagicMock:
        mock = MagicMock(spec=FileReaderPort)
        mock.get_info.return_value = FileInfo(
            path=FilePath("/test/sample.txt"),
            size=1024,
            mtime=1700000000,
            exists=True,
        )
        mock.read_content.return_value = FileContent(
            text="Sample content for testing. " * 100,
            file_type=FileType.from_extension(".txt"),
            success=True,
        )
        return mock

    @pytest.fixture
    def mock_compressor(self) -> MagicMock:
        mock = MagicMock(spec=TextCompressorPort)
        mock.compress.return_value = CompressionResult(
            data=b"compressed",
            original_size=100,
            compressed_size=50,
            compression_type=CompressionType.ZSTD,
        )
        return mock

    @pytest.fixture
    def use_case(
        self,
        mock_file_repo,
        mock_chunk_repo,
        mock_vector_store,
        mock_embedding,
        mock_file_reader,
        mock_compressor,
    ) -> IndexFileUseCase:
        return IndexFileUseCase(
            file_repository=mock_file_repo,
            chunk_repository=mock_chunk_repo,
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            file_reader=mock_file_reader,
            compressor=mock_compressor,
            enable_change_detection=True,
        )

    def test_index_new_file_success(self, use_case, mock_file_reader):
        result = use_case.execute("/test/sample.txt", index_content=True)

        assert result.success is True
        assert result.filename_indexed is True
        assert result.path == "/test/sample.txt"

    def test_index_nonexistent_file(self, use_case, mock_file_reader):
        mock_file_reader.get_info.return_value = FileInfo(
            path=FilePath("/test/missing.txt"),
            size=0,
            mtime=0,
            exists=False,
        )

        result = use_case.execute("/test/missing.txt")

        assert result.success is False
        assert result.error == "File does not exist"

    def test_skip_unchanged_file(self, use_case, mock_file_repo, mock_file_reader):
        existing = FileEntity(
            id=1,
            path=FilePath("/test/sample.txt"),
            file_type=FileType.from_extension(".txt"),
            size=1024,
            mtime=1700000000,
            status=IndexStatus.CONTENT_INDEXED,
            chunk_count=5,
        )
        mock_file_repo.find_by_path.return_value = existing

        result = use_case.execute("/test/sample.txt")

        assert result.success is True
        assert result.chunk_count == 5

    def test_embedding_failure(self, use_case, mock_embedding):
        mock_embedding.embed.return_value = None

        result = use_case.execute("/test/sample.txt")

        assert result.success is False
        assert result.filename_indexed is False

    def test_content_indexing_disabled(self, use_case):
        result = use_case.execute("/test/sample.txt", index_content=False)

        assert result.success is True
        assert result.filename_indexed is True
        assert result.content_indexed is False
        assert result.chunk_count == 0

class TestSearchUseCase:

    @pytest.fixture
    def mock_vector_store(self) -> MagicMock:
        mock = MagicMock(spec=VectorStorePort)
        mock.search.return_value = [
            VectorSearchHit(
                id="/test/file1.txt",
                distance=0.1,
                metadata={"path": "/test/file1.txt", "filename": "file1.txt"},
            ),
            VectorSearchHit(
                id="/test/file2.txt",
                distance=0.2,
                metadata={"path": "/test/file2.txt", "filename": "file2.txt"},
            ),
        ]
        return mock

    @pytest.fixture
    def mock_embedding(self) -> MagicMock:
        mock = MagicMock(spec=EmbeddingPort)
        mock.embed.return_value = EmbeddingVector([0.1] * 768)
        return mock

    @pytest.fixture
    def mock_chunk_repo(self) -> MagicMock:
        return MagicMock(spec=ChunkRepository)

    @pytest.fixture
    def mock_compressor(self) -> MagicMock:
        return MagicMock(spec=TextCompressorPort)

    @pytest.fixture
    def mock_search_history(self) -> MagicMock:
        mock = MagicMock(spec=SearchHistoryPort)
        mock.get_recent.return_value = []
        return mock

    @pytest.fixture
    def use_case(
        self,
        mock_vector_store,
        mock_embedding,
        mock_chunk_repo,
        mock_compressor,
        mock_search_history,
    ) -> SearchUseCase:
        return SearchUseCase(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            chunk_repository=mock_chunk_repo,
            compressor=mock_compressor,
            search_history=mock_search_history,
        )

    def test_filename_search(self, use_case, mock_vector_store):
        response = use_case.execute(
            query="test query",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        assert response.has_results is True
        assert len(response.results) == 2
        assert response.query == "test query"
        assert response.mode == SearchMode.FILENAME
        mock_vector_store.search.assert_called_once()

    def test_content_search(self, use_case, mock_vector_store):
        response = use_case.execute(
            query="semantic search",
            mode=SearchMode.CONTENT,
            top_k=20,
        )

        assert response.has_results is True
        assert response.mode == SearchMode.CONTENT

    def test_combined_search(self, use_case, mock_vector_store):
        response = use_case.execute(
            query="combined query",
            mode=SearchMode.COMBINED,
            top_k=20,
        )

        assert response.has_results is True
        assert response.mode == SearchMode.COMBINED
        assert mock_vector_store.search.call_count == 2

    def test_embedding_failure_returns_empty(self, use_case, mock_embedding):
        mock_embedding.embed.return_value = None

        response = use_case.execute(query="test")

        assert response.has_results is False
        assert len(response.results) == 0

    def test_search_history_recorded(self, use_case, mock_search_history):
        use_case.execute(query="test query")

        mock_search_history.add.assert_called_once()

    def test_get_search_history(self, use_case, mock_search_history):
        mock_search_history.get_recent.return_value = ["query1", "query2"]

        history = use_case.get_search_history(limit=10)

        assert len(history) == 2
        mock_search_history.get_recent.assert_called_once_with(10)

    def test_clear_search_history(self, use_case, mock_search_history):
        mock_search_history.clear.return_value = 5

        count = use_case.clear_search_history()

        assert count == 5
        mock_search_history.clear.assert_called_once()

class TestIndexFolderUseCase:

    @pytest.fixture
    def mock_folder_repo(self) -> MagicMock:
        mock = MagicMock(spec=FolderRepository)
        mock.save.side_effect = lambda e: e
        return mock

    @pytest.fixture
    def mock_file_reader(self) -> MagicMock:
        mock = MagicMock(spec=FileReaderPort)
        mock.is_directory.return_value = True
        mock.list_files.return_value = [
            FilePath("/test/folder/file1.txt"),
            FilePath("/test/folder/file2.py"),
            FilePath("/test/folder/file3.md"),
        ]
        return mock

    @pytest.fixture
    def mock_index_file_use_case(self) -> MagicMock:
        mock = MagicMock(spec=IndexFileUseCase)
        mock.execute.return_value = IndexFileResult(
            path="/test/file.txt",
            success=True,
            filename_indexed=True,
            content_indexed=True,
            chunk_count=3,
        )
        return mock

    @pytest.fixture
    def use_case(
        self,
        mock_folder_repo,
        mock_file_reader,
        mock_index_file_use_case,
    ) -> IndexFolderUseCase:
        return IndexFolderUseCase(
            folder_repository=mock_folder_repo,
            file_reader=mock_file_reader,
            index_file_use_case=mock_index_file_use_case,
        )

    def test_index_folder_success(self, use_case, mock_index_file_use_case):
        result = use_case.execute("/test/folder")

        assert result.total_files == 3
        assert result.indexed_files == 3
        assert result.failed_files == 0
        assert result.total_chunks == 9
        assert mock_index_file_use_case.execute.call_count == 3

    def test_index_nonexistent_folder(self, use_case, mock_file_reader):
        mock_file_reader.is_directory.return_value = False

        result = use_case.execute("/nonexistent/folder")

        assert result.total_files == 0
        assert "does not exist" in result.errors[0]

    def test_partial_failure(self, use_case, mock_index_file_use_case):
        mock_index_file_use_case.execute.side_effect = [
            IndexFileResult(
                path="/test/file1.txt",
                success=True,
                filename_indexed=True,
                content_indexed=True,
                chunk_count=3,
            ),
            IndexFileResult(
                path="/test/file2.txt",
                success=False,
                filename_indexed=False,
                content_indexed=False,
                chunk_count=0,
                error="Failed to read file",
            ),
            IndexFileResult(
                path="/test/file3.txt",
                success=True,
                filename_indexed=True,
                content_indexed=True,
                chunk_count=2,
            ),
        ]

        result = use_case.execute("/test/folder")

        assert result.indexed_files == 2
        assert result.failed_files == 1
        assert result.total_chunks == 5
        assert len(result.errors) == 1

    def test_progress_callback(self, use_case):
        progress_calls = []

        def progress_callback(path, current, total):
            progress_calls.append((path, current, total))

        use_case.execute("/test/folder", progress_callback=progress_callback)

        assert len(progress_calls) == 3
        assert progress_calls[0][1] == 1
        assert progress_calls[0][2] == 3
        assert progress_calls[2][1] == 3

    def test_success_rate(self, use_case, mock_index_file_use_case):
        mock_index_file_use_case.execute.side_effect = [
            IndexFileResult(
                path="/test/file1.txt",
                success=True,
                filename_indexed=True,
                content_indexed=True,
                chunk_count=1,
            ),
            IndexFileResult(
                path="/test/file2.txt",
                success=False,
                filename_indexed=False,
                content_indexed=False,
                chunk_count=0,
            ),
            IndexFileResult(
                path="/test/file3.txt",
                success=True,
                filename_indexed=True,
                content_indexed=True,
                chunk_count=1,
            ),
        ]

        result = use_case.execute("/test/folder")

        assert result.success_rate == pytest.approx(2 / 3)

    def test_get_indexed_folders(self, use_case, mock_folder_repo):
        mock_folder_repo.find_all.return_value = [
            FolderEntity(path="/folder1"),
            FolderEntity(path="/folder2"),
        ]

        folders = use_case.get_indexed_folders()

        assert len(folders) == 2
        mock_folder_repo.find_all.assert_called_once()

    def test_remove_folder(self, use_case, mock_folder_repo):
        mock_folder_repo.delete.return_value = True

        result = use_case.remove_folder("/test/folder")

        assert result is True
        mock_folder_repo.delete.assert_called_once_with("/test/folder")
