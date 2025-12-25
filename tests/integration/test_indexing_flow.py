
import os
import pytest

from src.domain.entities.file_entity import IndexStatus
from src.domain.constants import FILENAME_COLLECTION, CONTENT_COLLECTION
from .test_container import IntegrationContainer

class TestFileIndexingFlow:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def test_file(self, container: IntegrationContainer) -> str:
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "test_document.txt")

        content = """
        This is a test document for integration testing.
        It contains multiple paragraphs of text that will be
        processed during the indexing flow.

        The document should be chunked, embedded, and stored
        in both the metadata database and the vector store.

        Integration tests verify that all components work
        together correctly in a real-world scenario.
        """

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    def test_index_single_file_success(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case

        result = indexer.execute(test_file, index_content=True)

        assert result.success is True
        assert result.filename_indexed is True
        assert result.content_indexed is True
        assert result.chunk_count >= 1

    def test_file_stored_in_repository(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case
        indexer.execute(test_file)

        file_entity = container.file_repository.find_by_path(test_file)

        assert file_entity is not None
        assert file_entity.path.path == test_file
        assert file_entity.status == IndexStatus.CONTENT_INDEXED

    def test_chunks_stored_in_repository(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case
        result = indexer.execute(test_file)

        file_entity = container.file_repository.find_by_path(test_file)
        chunks = container.chunk_repository.find_by_file_id(file_entity.id)

        assert len(chunks) == result.chunk_count
        assert all(c.file_id == file_entity.id for c in chunks)

    def test_vectors_stored_in_vector_store(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case
        indexer.execute(test_file)

        filename_count = container.vector_store.count(FILENAME_COLLECTION)
        assert filename_count >= 1

        content_count = container.vector_store.count(CONTENT_COLLECTION)
        assert content_count >= 1

    def test_skip_unchanged_file(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case

        result1 = indexer.execute(test_file)
        assert result1.success is True

        result2 = indexer.execute(test_file)
        assert result2.success is True
        assert result2.chunk_count == result1.chunk_count

    def test_reindex_changed_file(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case

        result1 = indexer.execute(test_file)

        with open(test_file, "a", encoding="utf-8") as f:
            f.write("\n\nAdditional content added to the file.")

        file_entity = container.file_repository.find_by_path(test_file)
        file_entity.mtime = 0
        container.file_repository.save(file_entity)

        result2 = indexer.execute(test_file)
        assert result2.success is True

    def test_index_without_content(self, container: IntegrationContainer, test_file: str):
        indexer = container.index_file_use_case

        result = indexer.execute(test_file, index_content=False)

        assert result.success is True
        assert result.filename_indexed is True
        assert result.content_indexed is False
        assert result.chunk_count == 0

    def test_index_nonexistent_file(self, container: IntegrationContainer):
        indexer = container.index_file_use_case

        result = indexer.execute("/nonexistent/path/file.txt")

        assert result.success is False
        assert result.error == "File does not exist"

class TestFolderIndexingFlow:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def test_folder(self, container: IntegrationContainer) -> str:
        temp_dir = container.create_temp_dir()
        test_folder = os.path.join(temp_dir, "test_folder")
        os.makedirs(test_folder)

        files = [
            ("document1.txt", "This is the first test document."),
            ("document2.txt", "This is the second test document."),
            ("code.py", "def hello():\n    print('Hello, World!')"),
            ("readme.md", "# Test Project\n\nThis is a readme file."),
        ]

        for filename, content in files:
            file_path = os.path.join(test_folder, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        return test_folder

    def test_index_folder_success(self, container: IntegrationContainer, test_folder: str):
        indexer = container.index_folder_use_case

        result = indexer.execute(test_folder)

        assert result.total_files == 4
        assert result.indexed_files == 4
        assert result.failed_files == 0
        assert result.success_rate == 1.0

    def test_all_files_in_repository(self, container: IntegrationContainer, test_folder: str):
        indexer = container.index_folder_use_case
        indexer.execute(test_folder)

        file_count = container.file_repository.count()
        assert file_count == 4

    def test_folder_configuration_stored(self, container: IntegrationContainer, test_folder: str):
        indexer = container.index_folder_use_case
        indexer.execute(test_folder, include_hidden=False, index_content=True)

        folder = container.folder_repository.find_by_path(test_folder)

        assert folder is not None
        assert folder.settings.include_hidden is False
        assert folder.settings.index_content is True

    def test_progress_callback_called(self, container: IntegrationContainer, test_folder: str):
        indexer = container.index_folder_use_case
        progress_calls = []

        def progress_callback(path: str, current: int, total: int):
            progress_calls.append((path, current, total))

        indexer.execute(test_folder, progress_callback=progress_callback)

        assert len(progress_calls) == 4
        assert progress_calls[-1][1] == 4
        assert progress_calls[-1][2] == 4

    def test_index_nonexistent_folder(self, container: IntegrationContainer):
        indexer = container.index_folder_use_case

        result = indexer.execute("/nonexistent/folder")

        assert result.total_files == 0
        assert "does not exist" in result.errors[0]

    def test_nested_folder_structure(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        root_folder = os.path.join(temp_dir, "nested")
        os.makedirs(os.path.join(root_folder, "level1", "level2"))

        with open(os.path.join(root_folder, "root.txt"), "w") as f:
            f.write("Root level file")
        with open(os.path.join(root_folder, "level1", "level1.txt"), "w") as f:
            f.write("Level 1 file")
        with open(os.path.join(root_folder, "level1", "level2", "level2.txt"), "w") as f:
            f.write("Level 2 file")

        indexer = container.index_folder_use_case
        result = indexer.execute(root_folder)

        assert result.total_files == 3
        assert result.indexed_files == 3

    def test_exclude_hidden_files(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "with_hidden")
        os.makedirs(folder)

        with open(os.path.join(folder, "visible.txt"), "w") as f:
            f.write("Visible file")
        with open(os.path.join(folder, ".hidden"), "w") as f:
            f.write("Hidden file")

        indexer = container.index_folder_use_case
        result = indexer.execute(folder, include_hidden=False)

        assert result.total_files == 1

    def test_include_hidden_files(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "with_hidden")
        os.makedirs(folder)

        with open(os.path.join(folder, "visible.txt"), "w") as f:
            f.write("Visible file")
        with open(os.path.join(folder, ".hidden"), "w") as f:
            f.write("Hidden file")

        indexer = container.index_folder_use_case
        result = indexer.execute(folder, include_hidden=True)

        assert result.total_files == 2

    def test_remove_indexed_folder(self, container: IntegrationContainer, test_folder: str):
        indexer = container.index_folder_use_case
        indexer.execute(test_folder)

        assert container.folder_repository.count() == 1

        removed = indexer.remove_folder(test_folder)

        assert removed is True
        assert container.folder_repository.count() == 0

    def test_get_indexed_folders(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        folder1 = os.path.join(temp_dir, "folder1")
        folder2 = os.path.join(temp_dir, "folder2")
        os.makedirs(folder1)
        os.makedirs(folder2)

        with open(os.path.join(folder1, "test1.txt"), "w") as f:
            f.write("Test 1")
        with open(os.path.join(folder2, "test2.txt"), "w") as f:
            f.write("Test 2")

        indexer = container.index_folder_use_case
        indexer.execute(folder1)
        indexer.execute(folder2)

        folders = indexer.get_indexed_folders()

        assert len(folders) == 2
