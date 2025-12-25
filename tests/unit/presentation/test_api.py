
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.presentation.api import create_app
from src.presentation.api.routes import _app_service, get_app_service
from src.presentation.api import routes


class TestAPIEndpoints:
    """Tests for REST API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset app service before each test."""
        routes._app_service = None
        yield
        if routes._app_service is not None:
            routes._app_service.close()
            routes._app_service = None

    @pytest.fixture
    def client(self):
        app = create_app()
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def temp_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("This is test content for API testing.")
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Local Semantic Explorer API"
        assert "version" in data
        assert data["docs"] == "/docs"

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_status_endpoint(self, client: TestClient):
        """Test status endpoint returns service status."""
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "indexed_files" in data
        assert "indexed_chunks" in data
        assert "watched_folders" in data

    def test_search_endpoint(self, client: TestClient, temp_file: str):
        """Test search endpoint."""
        # First index a file
        client.post(
            "/api/v1/index/file",
            json={"file_path": temp_file, "index_content": True},
        )

        # Then search
        response = client.post(
            "/api/v1/search",
            json={
                "query": "test content",
                "mode": "filename",
                "top_k": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test content"
        assert data["mode"] == "filename"
        assert "results" in data
        assert "total_count" in data

    def test_search_with_invalid_mode(self, client: TestClient):
        """Test search with invalid mode returns error."""
        response = client.post(
            "/api/v1/search",
            json={
                "query": "test",
                "mode": "invalid_mode",
                "top_k": 10,
            },
        )

        assert response.status_code == 422  # Validation error

    def test_search_with_empty_query(self, client: TestClient):
        """Test search with empty query returns error."""
        response = client.post(
            "/api/v1/search",
            json={
                "query": "",
                "mode": "filename",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_index_file_endpoint(self, client: TestClient, temp_file: str):
        """Test indexing a file via API."""
        response = client.post(
            "/api/v1/index/file",
            json={"file_path": temp_file, "index_content": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["path"] == temp_file

    def test_index_nonexistent_file(self, client: TestClient):
        """Test indexing a nonexistent file returns error."""
        response = client.post(
            "/api/v1/index/file",
            json={"file_path": "/nonexistent/file.txt"},
        )

        # Should return success=False, not 404
        # Because the use case handles missing files gracefully
        data = response.json()
        assert data["success"] is False

    def test_index_folder_endpoint(self, client: TestClient):
        """Test indexing a folder via API."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            for i in range(3):
                file_path = os.path.join(temp_dir, f"test_{i}.txt")
                with open(file_path, "w") as f:
                    f.write(f"Content of file {i}")

            response = client.post(
                "/api/v1/index/folder",
                json={
                    "folder_path": temp_dir,
                    "include_hidden": False,
                    "index_content": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["indexed_count"] == 3
            assert data["total_count"] == 3

    def test_remove_file_endpoint(self, client: TestClient, temp_file: str):
        """Test removing a file from index."""
        # First index the file
        client.post(
            "/api/v1/index/file",
            json={"file_path": temp_file},
        )

        # Then remove it
        response = client.delete(
            "/api/v1/index/file",
            params={"file_path": temp_file},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_watch_endpoints(self, client: TestClient):
        """Test folder watching endpoints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Start watching
            response = client.post(
                "/api/v1/watch/start",
                params={"folder_path": temp_dir},
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

            # Check status shows watched folder
            status = client.get("/api/v1/status").json()
            assert temp_dir in status["watched_folders"]

            # Stop watching
            response = client.post("/api/v1/watch/stop")

            assert response.status_code == 200
            assert response.json()["success"] is True


class TestAPISearchModes:
    """Tests for different search modes via API."""

    @pytest.fixture(autouse=True)
    def setup(self):
        routes._app_service = None
        yield
        if routes._app_service is not None:
            routes._app_service.close()
            routes._app_service = None

    @pytest.fixture
    def client(self):
        app = create_app()
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def indexed_files(self, client: TestClient):
        with tempfile.TemporaryDirectory() as temp_dir:
            files = []
            test_data = [
                ("readme.md", "# README\nThis is documentation."),
                ("main.py", "def main():\n    print('Hello')"),
                ("config.json", '{"key": "value"}'),
            ]

            for filename, content in test_data:
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w") as f:
                    f.write(content)
                files.append(file_path)

                client.post(
                    "/api/v1/index/file",
                    json={"file_path": file_path, "index_content": True},
                )

            yield files

    def test_filename_search_mode(self, client: TestClient, indexed_files: list):
        """Test filename search mode."""
        response = client.post(
            "/api/v1/search",
            json={"query": "readme", "mode": "filename"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "filename"
        assert len(data["results"]) > 0

    def test_content_search_mode(self, client: TestClient, indexed_files: list):
        """Test content search mode."""
        response = client.post(
            "/api/v1/search",
            json={"query": "documentation", "mode": "content"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "content"

    def test_combined_search_mode(self, client: TestClient, indexed_files: list):
        """Test combined search mode."""
        response = client.post(
            "/api/v1/search",
            json={"query": "main python", "mode": "combined"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "combined"

    def test_top_k_parameter(self, client: TestClient, indexed_files: list):
        """Test top_k parameter limits results."""
        response = client.post(
            "/api/v1/search",
            json={"query": "file", "mode": "filename", "top_k": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 1
