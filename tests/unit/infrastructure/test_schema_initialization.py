
import os
import sqlite3
import tempfile

import pytest

from src.infrastructure.persistence.sqlite.connection import SqliteConnectionManager


class TestSchemaInitialization:
    """Tests for verifying that all adapter schemas are properly initialized.

    This test class specifically verifies the fix for the schema skip bug where
    only the first adapter's schema was initialized due to the _initialized flag.
    """

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield db_path

    def test_multiple_schemas_all_initialized(self, temp_db: str):
        """Verify that multiple schema initializations all succeed."""
        conn_manager = SqliteConnectionManager(temp_db)

        # First schema (simulates FileRepository)
        schema1 = """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL
        );
        """

        # Second schema (simulates SearchHistoryAdapter)
        schema2 = """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY,
            query TEXT NOT NULL
        );
        """

        # Third schema (simulates ChunkRepository)
        schema3 = """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL
        );
        """

        # Initialize all schemas
        conn_manager.initialize_schema(schema1)
        conn_manager.initialize_schema(schema2)
        conn_manager.initialize_schema(schema3)

        # Verify all tables exist
        conn = conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "files" in tables, "files table should exist"
        assert "search_history" in tables, "search_history table should exist"
        assert "chunks" in tables, "chunks table should exist"

        conn_manager.close()

    def test_schema_initialization_order_independent(self, temp_db: str):
        """Verify schema initialization works regardless of order."""
        conn_manager = SqliteConnectionManager(temp_db)

        # Initialize in different order
        conn_manager.initialize_schema(
            "CREATE TABLE IF NOT EXISTS table_c (id INTEGER PRIMARY KEY);"
        )
        conn_manager.initialize_schema(
            "CREATE TABLE IF NOT EXISTS table_a (id INTEGER PRIMARY KEY);"
        )
        conn_manager.initialize_schema(
            "CREATE TABLE IF NOT EXISTS table_b (id INTEGER PRIMARY KEY);"
        )

        conn = conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "table_a" in tables
        assert "table_b" in tables
        assert "table_c" in tables

        conn_manager.close()

    def test_duplicate_schema_initialization_safe(self, temp_db: str):
        """Verify that initializing the same schema twice is safe."""
        conn_manager = SqliteConnectionManager(temp_db)

        schema = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY,
            data TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_test ON test_table(data);
        """

        # Initialize same schema multiple times
        conn_manager.initialize_schema(schema)
        conn_manager.initialize_schema(schema)
        conn_manager.initialize_schema(schema)

        # Should not raise and table should exist
        conn = conn_manager.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM test_table")
        assert cursor.fetchone()[0] == 0

        conn_manager.close()

    def test_schema_with_indexes_and_triggers(self, temp_db: str):
        """Verify complex schemas with indexes are properly initialized."""
        conn_manager = SqliteConnectionManager(temp_db)

        schema1 = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        );
        CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
        """

        schema2 = """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            content TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id);
        """

        conn_manager.initialize_schema(schema1)
        conn_manager.initialize_schema(schema2)

        # Verify tables and indexes exist
        conn = conn_manager.get_connection()

        # Check tables
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "users" in tables
        assert "posts" in tables

        # Check indexes
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_users_name" in indexes
        assert "idx_posts_user" in indexes

        conn_manager.close()


class TestRealAdapterSchemaInitialization:
    """Integration tests using real adapter classes."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            yield db_path

    def test_all_real_adapters_schemas_initialized(self, temp_db: str):
        """Verify all real adapter schemas are properly initialized."""
        from src.infrastructure.persistence.sqlite import (
            SqliteConnectionManager,
            SqliteFileRepository,
            SqliteChunkRepository,
            SqliteFolderRepository,
            SqliteSearchHistoryAdapter,
        )
        from src.infrastructure.persistence.sqlite.fts_search_adapter import (
            SqliteFTS5Adapter,
        )

        conn_manager = SqliteConnectionManager(temp_db)

        # Initialize all adapters (each calls initialize_schema)
        file_repo = SqliteFileRepository(conn_manager)
        chunk_repo = SqliteChunkRepository(conn_manager)
        folder_repo = SqliteFolderRepository(conn_manager)
        search_history = SqliteSearchHistoryAdapter(conn_manager)
        fts_adapter = SqliteFTS5Adapter(conn_manager)

        # Verify all required tables exist
        conn = conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        # Core tables
        assert "files" in tables, "files table missing"
        assert "chunks" in tables, "chunks table missing"
        assert "indexed_folders" in tables, "indexed_folders table missing"
        assert "search_history" in tables, "search_history table missing"

        # FTS virtual table
        assert "content_fts" in tables, "content_fts table missing"

        conn_manager.close()

    def test_search_history_usable_after_file_repo_init(self, temp_db: str):
        """Verify search_history works even when initialized after file_repository.

        This is the specific bug scenario that was fixed:
        1. FileRepository initializes first, sets _initialized = True
        2. SearchHistoryAdapter schema was skipped
        3. Querying search_history would fail with 'no such table'
        """
        from src.infrastructure.persistence.sqlite import (
            SqliteConnectionManager,
            SqliteFileRepository,
            SqliteSearchHistoryAdapter,
        )
        from src.domain.value_objects.search_query import SearchMode

        conn_manager = SqliteConnectionManager(temp_db)

        # Initialize file repository first (was causing the bug)
        file_repo = SqliteFileRepository(conn_manager)

        # Then initialize search history (was skipped before fix)
        search_history = SqliteSearchHistoryAdapter(conn_manager)

        # This should work without "no such table: search_history" error
        entry = search_history.add(
            query="test query",
            mode=SearchMode.FILENAME,
            result_count=5,
        )

        assert entry.id is not None
        assert entry.query == "test query"

        # Verify we can retrieve it
        history = search_history.get_recent(limit=10)
        assert len(history) == 1
        assert history[0].query == "test query"

        conn_manager.close()
