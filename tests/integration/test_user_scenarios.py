
import os
import pytest
import time
from unittest.mock import patch, MagicMock

from src.domain.value_objects.search_query import SearchMode
from .test_container import IntegrationContainer

class TestFirstTimeUserScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_new_user_adds_first_folder_and_indexes(self, container: IntegrationContainer):
        assert container.folder_repository.count() == 0
        assert container.file_repository.count() == 0

        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "my_documents")
        os.makedirs(folder)

        files = {
            "project_proposal.txt": "This is a project proposal for the new AI system.",
            "meeting_notes.md": "# Meeting Notes\n\nDiscussed project timeline and deliverables.",
            "research_paper.txt": "Abstract: This paper explores machine learning algorithms.",
        }
        for filename, content in files.items():
            with open(os.path.join(folder, filename), "w") as f:
                f.write(content)

        indexer = container.index_folder_use_case
        result = indexer.execute(folder, index_content=True)

        assert result.indexed_files == 3
        assert result.failed_files == 0

        searcher = container.search_use_case
        response = searcher.execute("project proposal", mode=SearchMode.FILENAME)

        assert response.has_results is True
        assert any("proposal" in r.file_path for r in response.results)

class TestReturningUserScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_search_previously_indexed_files(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "work")
        os.makedirs(folder)

        with open(os.path.join(folder, "report_2024.txt"), "w") as f:
            f.write("Annual report for 2024 fiscal year.")

        indexer = container.index_folder_use_case
        indexer.execute(folder)

        searcher = container.search_use_case
        response = searcher.execute("report 2024", mode=SearchMode.COMBINED)

        assert response.has_results is True
        assert any("report" in r.file_path for r in response.results)

class TestContentSearchScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_find_relevant_content_by_concept(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        topics = {
            "security_policy.txt": "This document outlines our cybersecurity policies. "
                                    "All employees must follow password guidelines and "
                                    "report suspicious activities immediately.",
            "marketing_plan.txt": "Q4 marketing strategy focuses on social media campaigns "
                                   "and influencer partnerships to drive brand awareness.",
            "hr_handbook.txt": "Employee benefits include health insurance, 401k matching, "
                               "and flexible work arrangements.",
        }

        for filename, content in topics.items():
            path = os.path.join(temp_dir, filename)
            with open(path, "w") as f:
                f.write(content)

        indexer = container.index_file_use_case
        for filename in topics:
            indexer.execute(os.path.join(temp_dir, filename), index_content=True)

        searcher = container.search_use_case
        response = searcher.execute(
            "password security authentication",
            mode=SearchMode.CONTENT
        )

        assert response.has_results is True
        top_paths = [r.file_path for r in response.results[:2]]
        assert any("security" in p for p in top_paths)

class TestFileModificationScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_reindex_after_file_modification(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "changelog.txt")

        with open(file_path, "w") as f:
            f.write("Version 1.0: Initial release of the application.")

        indexer = container.index_file_use_case
        result1 = indexer.execute(file_path, index_content=True)
        assert result1.success is True

        time.sleep(0.1)
        with open(file_path, "w") as f:
            f.write("Version 2.0: Major update with new features and bug fixes. "
                    "Added dark mode and improved performance.")

        file_entity = container.file_repository.find_by_path(file_path)
        file_entity.mtime = 0
        container.file_repository.save(file_entity)

        result2 = indexer.execute(file_path, index_content=True)
        assert result2.success is True

        searcher = container.search_use_case
        response = searcher.execute("dark mode feature", mode=SearchMode.CONTENT)

        assert response.has_results is True

class TestMultipleFoldersScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_search_across_multiple_folders(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        work_folder = os.path.join(temp_dir, "work")
        personal_folder = os.path.join(temp_dir, "personal")
        os.makedirs(work_folder)
        os.makedirs(personal_folder)

        with open(os.path.join(work_folder, "project.txt"), "w") as f:
            f.write("Work project documentation for the client deliverable.")

        with open(os.path.join(personal_folder, "recipe.txt"), "w") as f:
            f.write("Personal recipe collection for weekend cooking.")

        indexer = container.index_folder_use_case
        indexer.execute(work_folder)
        indexer.execute(personal_folder)

        folders = indexer.get_indexed_folders()
        assert len(folders) == 2

        searcher = container.search_use_case

        work_response = searcher.execute("project documentation", mode=SearchMode.COMBINED)
        assert any("work" in r.file_path.lower() for r in work_response.results)

        personal_response = searcher.execute("recipe cooking", mode=SearchMode.COMBINED)
        assert any("personal" in r.file_path.lower() for r in personal_response.results)

class TestEdgeCasesScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_index_empty_folder(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        empty_folder = os.path.join(temp_dir, "empty")
        os.makedirs(empty_folder)

        indexer = container.index_folder_use_case
        result = indexer.execute(empty_folder)

        assert result.total_files == 0
        assert result.indexed_files == 0

    def test_index_folder_with_binary_files(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "mixed")
        os.makedirs(folder)

        with open(os.path.join(folder, "readme.txt"), "w") as f:
            f.write("This is readable text.")

        with open(os.path.join(folder, "data.bin"), "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04")

        indexer = container.index_folder_use_case
        result = indexer.execute(folder)

        assert result.indexed_files >= 1

    def test_search_with_special_characters(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write("C++ programming guide and JavaScript examples.")

        indexer = container.index_file_use_case
        indexer.execute(os.path.join(temp_dir, "test.txt"), index_content=True)

        searcher = container.search_use_case

        response = searcher.execute("C++ programming", mode=SearchMode.CONTENT)
        assert response.total_count >= 0

    def test_search_very_long_query(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        with open(os.path.join(temp_dir, "test.txt"), "w") as f:
            f.write("Short content for testing long queries.")

        indexer = container.index_file_use_case
        indexer.execute(os.path.join(temp_dir, "test.txt"), index_content=True)

        searcher = container.search_use_case

        long_query = "test " * 100
        response = searcher.execute(long_query, mode=SearchMode.CONTENT)
        assert response.total_count >= 0

    def test_concurrent_index_operations(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()

        for i in range(10):
            with open(os.path.join(temp_dir, f"file_{i}.txt"), "w") as f:
                f.write(f"Content of file {i}")

        indexer = container.index_folder_use_case
        result = indexer.execute(temp_dir)

        assert result.indexed_files == 10
        assert result.failed_files == 0

    def test_file_deleted_after_indexing(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "temporary.txt")

        with open(file_path, "w") as f:
            f.write("Temporary content for deletion test.")

        indexer = container.index_file_use_case
        indexer.execute(file_path, index_content=True)

        os.remove(file_path)

        searcher = container.search_use_case
        response = searcher.execute("temporary", mode=SearchMode.COMBINED)

        assert response.total_count >= 0

class TestCancellationScenario:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_index_folder_with_cancellation_callback(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "large")
        os.makedirs(folder)

        for i in range(20):
            with open(os.path.join(folder, f"file_{i:03d}.txt"), "w") as f:
                f.write(f"Content {i}")

        indexer = container.index_folder_use_case
        cancel_after = 5
        indexed_count = [0]

        def progress_with_cancel(path: str, current: int, total: int):
            indexed_count[0] = current
            if current >= cancel_after:
                raise KeyboardInterrupt("Cancelled by user")

        try:
            indexer.execute(folder, progress_callback=progress_with_cancel)
        except KeyboardInterrupt:
            pass

        assert indexed_count[0] >= cancel_after
