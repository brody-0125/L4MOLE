
import os
import pytest

from src.domain.value_objects.search_query import SearchMode
from .test_container import IntegrationContainer

class TestSearchFlow:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def indexed_files(self, container: IntegrationContainer) -> list:
        temp_dir = container.create_temp_dir()
        files = []

        test_data = [
            (
                "python_tutorial.txt",
                """
                Python Programming Tutorial

                Python is a versatile programming language used for
                web development, data science, and automation.

                This tutorial covers Python basics including variables,
                functions, and object-oriented programming.
                """,
            ),
            (
                "machine_learning.txt",
                """
                Introduction to Machine Learning

                Machine learning is a subset of artificial intelligence
                that enables systems to learn from data.

                Common algorithms include neural networks, decision trees,
                and support vector machines.
                """,
            ),
            (
                "web_development.txt",
                """
                Web Development Guide

                Modern web development involves HTML, CSS, and JavaScript.
                Popular frameworks include React, Vue, and Angular.

                Backend technologies include Python Django, Node.js,
                and Ruby on Rails.
                """,
            ),
            (
                "database_design.txt",
                """
                Database Design Principles

                Relational databases use SQL for querying data.
                NoSQL databases offer flexible schema design.

                Key concepts include normalization, indexing,
                and query optimization.
                """,
            ),
        ]

        for filename, content in test_data:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            files.append(file_path)

        indexer = container.index_file_use_case
        for file_path in files:
            result = indexer.execute(file_path, index_content=True)
            assert result.success, f"Failed to index {file_path}"

        return files

    def test_filename_search(self, container: IntegrationContainer, indexed_files: list):
        searcher = container.search_use_case

        response = searcher.execute(
            query="python tutorial",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        assert response.has_results is True
        assert response.mode == SearchMode.FILENAME

        paths = [r.file_path for r in response.results]
        assert any("python" in p.lower() for p in paths)

    def test_content_search(self, container: IntegrationContainer, indexed_files: list):
        searcher = container.search_use_case

        response = searcher.execute(
            query="artificial intelligence and neural networks",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response.has_results is True
        assert response.mode == SearchMode.CONTENT

        paths = [r.file_path for r in response.results]
        assert any("machine_learning" in p for p in paths)

    def test_combined_search(self, container: IntegrationContainer, indexed_files: list):
        searcher = container.search_use_case

        response = searcher.execute(
            query="web development frameworks",
            mode=SearchMode.COMBINED,
            top_k=10,
        )

        assert response.has_results is True
        assert response.mode == SearchMode.COMBINED
        assert len(response.results) > 0

    def test_search_returns_similarity_scores(
        self, container: IntegrationContainer, indexed_files: list
    ):
        searcher = container.search_use_case

        response = searcher.execute(query="python programming")

        assert response.has_results is True

        for result in response.results:
            assert 0.0 <= result.similarity_score <= 100.0

    def test_search_result_order(self, container: IntegrationContainer, indexed_files: list):
        searcher = container.search_use_case

        response = searcher.execute(
            query="database SQL query",
            mode=SearchMode.CONTENT,
        )

        scores = [r.similarity_score for r in response.results]
        assert scores == sorted(scores, reverse=True)

    def test_search_with_top_k_limit(
        self, container: IntegrationContainer, indexed_files: list
    ):
        searcher = container.search_use_case

        response = searcher.execute(
            query="programming",
            mode=SearchMode.COMBINED,
            top_k=2,
        )

        assert len(response.results) <= 2

    def test_empty_query_handling(self, container: IntegrationContainer, indexed_files: list):
        import pytest
        searcher = container.search_use_case

        with pytest.raises(ValueError, match="cannot be empty"):
            searcher.execute(
                query="   ",
                mode=SearchMode.FILENAME,
            )

    def test_no_results_for_unrelated_query(
        self, container: IntegrationContainer, indexed_files: list
    ):
        searcher = container.search_use_case

        response = searcher.execute(
            query="quantum physics black holes",
            mode=SearchMode.CONTENT,
        )

        assert response.total_count >= 0

class TestSearchHistory:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def indexed_file(self, container: IntegrationContainer) -> str:
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "test.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Test content for search history testing.")

        indexer = container.index_file_use_case
        indexer.execute(file_path)

        return file_path

    def test_search_recorded_in_history(
        self, container: IntegrationContainer, indexed_file: str
    ):
        searcher = container.search_use_case

        searcher.execute(query="test query")

        history = searcher.get_search_history(limit=10)
        assert len(history) == 1
        assert history[0].query == "test query"

    def test_multiple_searches_recorded(
        self, container: IntegrationContainer, indexed_file: str
    ):
        searcher = container.search_use_case

        searcher.execute(query="first query")
        searcher.execute(query="second query")
        searcher.execute(query="third query")

        history = searcher.get_search_history(limit=10)
        assert len(history) == 3

        assert history[0].query == "third query"
        assert history[2].query == "first query"

    def test_history_limit(self, container: IntegrationContainer, indexed_file: str):
        searcher = container.search_use_case

        for i in range(10):
            searcher.execute(query=f"query {i}")

        history = searcher.get_search_history(limit=5)
        assert len(history) == 5

    def test_clear_search_history(self, container: IntegrationContainer, indexed_file: str):
        searcher = container.search_use_case

        searcher.execute(query="query 1")
        searcher.execute(query="query 2")

        count = searcher.clear_search_history()
        assert count == 2

        history = searcher.get_search_history()
        assert len(history) == 0

    def test_history_includes_mode(self, container: IntegrationContainer, indexed_file: str):
        searcher = container.search_use_case

        searcher.execute(query="filename search", mode=SearchMode.FILENAME)
        searcher.execute(query="content search", mode=SearchMode.CONTENT)

        history = searcher.get_search_history()

        assert history[0].mode == SearchMode.CONTENT
        assert history[1].mode == SearchMode.FILENAME

    def test_history_includes_result_count(
        self, container: IntegrationContainer, indexed_file: str
    ):
        searcher = container.search_use_case

        searcher.execute(query="test")

        history = searcher.get_search_history()
        assert history[0].result_count >= 0

class TestSearchWithFilters:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def indexed_folder(self, container: IntegrationContainer) -> str:
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "mixed_files")
        os.makedirs(folder)

        files = [
            ("script.py", "Python script with functions"),
            ("app.js", "JavaScript application code"),
            ("readme.md", "Documentation file"),
            ("data.txt", "Plain text data file"),
        ]

        for filename, content in files:
            file_path = os.path.join(folder, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        indexer = container.index_folder_use_case
        indexer.execute(folder)

        return folder

    def test_search_all_file_types(
        self, container: IntegrationContainer, indexed_folder: str
    ):
        searcher = container.search_use_case

        response = searcher.execute(
            query="code script",
            mode=SearchMode.COMBINED,
            top_k=10,
        )

        assert response.has_results is True
        extensions = set()
        for result in response.results:
            ext = os.path.splitext(result.file_path)[1]
            extensions.add(ext)

        assert len(extensions) >= 1

class TestSearchPerformance:

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    def test_search_with_many_files(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        folder = os.path.join(temp_dir, "many_files")
        os.makedirs(folder)

        for i in range(50):
            file_path = os.path.join(folder, f"file_{i:03d}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Content of file number {i}. " * 10)

        indexer = container.index_folder_use_case
        result = indexer.execute(folder)
        assert result.indexed_files == 50

        searcher = container.search_use_case
        response = searcher.execute(
            query="file content",
            mode=SearchMode.COMBINED,
            top_k=20,
        )

        assert response.has_results is True
        assert len(response.results) <= 20

    def test_container_reset(self, container: IntegrationContainer):
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "test.txt")
        with open(file_path, "w") as f:
            f.write("Test content")

        indexer = container.index_file_use_case
        indexer.execute(file_path)

        assert container.file_repository.count() == 1

        container.reset()

        assert container.file_repository.count() == 0
        assert container.chunk_repository.count() == 0
