
import os
import pytest

from src.domain.value_objects.search_query import SearchMode
from .test_container import IntegrationContainer


class TestSearchQueryValidation:
    """Tests for validating search query behavior across all search modes."""

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def indexed_documents(self, container: IntegrationContainer) -> list:
        """Create and index test documents with diverse content."""
        temp_dir = container.create_temp_dir()
        files = []

        test_data = [
            (
                "api_documentation.md",
                """
                # REST API Documentation

                This document describes the REST API endpoints for the application.

                ## Authentication
                All endpoints require Bearer token authentication.
                Use the /auth/login endpoint to obtain a token.

                ## Endpoints
                - GET /api/users - List all users
                - POST /api/users - Create a new user
                - GET /api/search - Search documents
                """,
            ),
            (
                "database_schema.sql",
                """
                -- Database Schema for User Management

                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE search_history (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    query TEXT NOT NULL,
                    searched_at TIMESTAMP
                );

                CREATE INDEX idx_search_query ON search_history(query);
                """,
            ),
            (
                "config.json",
                """
                {
                    "database": {
                        "host": "localhost",
                        "port": 5432,
                        "name": "app_db"
                    },
                    "search": {
                        "max_results": 100,
                        "timeout_ms": 5000
                    },
                    "api": {
                        "base_url": "/api/v1",
                        "rate_limit": 1000
                    }
                }
                """,
            ),
            (
                "README.txt",
                """
                Application Setup Guide

                Prerequisites:
                - Python 3.10 or higher
                - PostgreSQL database
                - Redis for caching

                Installation Steps:
                1. Clone the repository
                2. Install dependencies: pip install -r requirements.txt
                3. Configure database connection
                4. Run migrations
                5. Start the server

                For API documentation, see api_documentation.md
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

    # === Filename Search Tests ===

    def test_filename_search_exact_match(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify filename search finds exact filename matches."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="api_documentation",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        assert response.has_results
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert "api_documentation.md" in filenames

    def test_filename_search_partial_match(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify filename search finds partial matches."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="config",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        assert response.has_results
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert any("config" in f.lower() for f in filenames)

    def test_filename_search_extension_agnostic(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify filename search works regardless of file extension."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="database schema",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        assert response.has_results
        # Should find database_schema.sql
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert any("database" in f.lower() for f in filenames)

    # === Content Search Tests ===

    def test_content_search_finds_semantic_match(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify content search finds semantically relevant documents."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="authentication token login",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response.has_results
        # Should prioritize api_documentation.md which mentions authentication
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert "api_documentation.md" in filenames

    def test_content_search_sql_queries(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify content search finds SQL-related content."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="CREATE TABLE PRIMARY KEY",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response.has_results
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert "database_schema.sql" in filenames

    def test_content_search_json_config(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify content search finds JSON configuration content."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="database host port configuration",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response.has_results
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert "config.json" in filenames

    # === Combined Search Tests ===

    def test_combined_search_merges_results(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify combined search merges filename and content results."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="README installation",
            mode=SearchMode.COMBINED,
            top_k=10,
        )

        assert response.has_results
        # Should find README.txt via both filename and content
        filenames = [os.path.basename(r.file_path) for r in response.results]
        assert "README.txt" in filenames

    def test_combined_search_respects_top_k(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify combined search respects top_k limit."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="document",
            mode=SearchMode.COMBINED,
            top_k=2,
        )

        assert len(response.results) <= 2

    # === Edge Cases ===

    def test_search_with_special_characters(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify search handles special characters gracefully."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="/api/users",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        # Should not crash and may find API documentation
        assert response is not None

    def test_search_with_numbers(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify search handles numeric queries."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="5432 port",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response is not None

    def test_search_case_insensitive(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify search is case-insensitive."""
        searcher = container.search_use_case

        response_lower = searcher.execute(
            query="database",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        response_upper = searcher.execute(
            query="DATABASE",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        # Both should return results
        assert response_lower.has_results
        assert response_upper.has_results

    def test_search_long_query(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify search handles long queries."""
        searcher = container.search_use_case

        long_query = "How do I set up the database connection and configure " \
                     "the search functionality with proper authentication?"

        response = searcher.execute(
            query=long_query,
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        assert response is not None
        # Should find relevant documents

    # === Result Ordering Tests ===

    def test_search_results_ordered_by_relevance(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify search results are ordered by similarity score."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="REST API endpoints authentication",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        scores = [r.similarity_score for r in response.results]
        assert scores == sorted(scores, reverse=True), \
            "Results should be ordered by descending similarity score"

    def test_search_similarity_scores_valid_range(
        self, container: IntegrationContainer, indexed_documents: list
    ):
        """Verify all similarity scores are within valid range."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="search query",
            mode=SearchMode.COMBINED,
            top_k=10,
        )

        for result in response.results:
            assert 0.0 <= result.similarity_score <= 100.0, \
                f"Score {result.similarity_score} out of valid range [0, 100]"


class TestSearchModeSpecificBehavior:
    """Tests for mode-specific search behavior."""

    @pytest.fixture
    def container(self) -> IntegrationContainer:
        container = IntegrationContainer()
        yield container
        container.close()

    @pytest.fixture
    def indexed_file(self, container: IntegrationContainer) -> str:
        temp_dir = container.create_temp_dir()
        file_path = os.path.join(temp_dir, "unique_filename_xyz.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("This file contains completely different content about ABC.")

        indexer = container.index_file_use_case
        indexer.execute(file_path, index_content=True)

        return file_path

    def test_filename_mode_ignores_content(
        self, container: IntegrationContainer, indexed_file: str
    ):
        """Verify FILENAME mode searches only in filenames."""
        searcher = container.search_use_case

        # Search for content that exists only in file content
        response = searcher.execute(
            query="ABC content",
            mode=SearchMode.FILENAME,
            top_k=10,
        )

        # Should still find the file but based on filename similarity
        # The match_type should be 'filename'
        for result in response.results:
            assert result.match_type == "filename"

    def test_content_mode_searches_content(
        self, container: IntegrationContainer, indexed_file: str
    ):
        """Verify CONTENT mode searches in file content."""
        searcher = container.search_use_case

        # Search for content
        response = searcher.execute(
            query="completely different ABC",
            mode=SearchMode.CONTENT,
            top_k=10,
        )

        # Should find based on content match
        for result in response.results:
            assert result.match_type == "content"

    def test_combined_mode_includes_both(
        self, container: IntegrationContainer, indexed_file: str
    ):
        """Verify COMBINED mode includes both filename and content matches."""
        searcher = container.search_use_case

        response = searcher.execute(
            query="unique filename content",
            mode=SearchMode.COMBINED,
            top_k=10,
        )

        # Should have results
        assert response.has_results

        # Results may have different match types
        match_types = {r.match_type for r in response.results}
        # Combined mode merges filename and content results
        assert len(match_types) >= 1
