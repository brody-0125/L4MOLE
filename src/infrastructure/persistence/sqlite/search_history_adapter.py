
import logging
from datetime import datetime
from typing import List

from ....domain.ports.search_history_port import (
    SearchHistoryEntry,
    SearchHistoryPort,
)
from ....domain.value_objects.search_query import SearchMode
from .connection import SqliteConnectionManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Search history
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    result_count INTEGER DEFAULT 0,
    searched_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_search_history_query ON search_history(query);
CREATE INDEX IF NOT EXISTS idx_search_history_time ON search_history(searched_at);
"""

class SqliteSearchHistoryAdapter(SearchHistoryPort):

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._conn_manager = connection_manager
        self._conn_manager.initialize_schema(SCHEMA_SQL)

    def _row_to_entry(self, row) -> SearchHistoryEntry:
        return SearchHistoryEntry(
            id=row["id"],
            query=row["query"],
            mode=SearchMode(row["mode"]),
            result_count=row["result_count"],
            searched_at=datetime.fromtimestamp(row["searched_at"]),
        )

    def add(
        self,
        query: str,
        mode: SearchMode,
        result_count: int,
    ) -> SearchHistoryEntry:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO search_history (query, mode, result_count)
                VALUES (?, ?, ?)
                """,
                (query, mode.value, result_count),
            )

            return SearchHistoryEntry(
                id=cursor.lastrowid,
                query=query,
                mode=mode,
                result_count=result_count,
                searched_at=datetime.now(),
            )

    def get_recent(self, limit: int = 50) -> List[SearchHistoryEntry]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM search_history
            ORDER BY searched_at DESC
            LIMIT ?
            """,
            (limit,),
        )

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def clear(self) -> int:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute("DELETE FROM search_history")
            return cursor.rowcount

    def find_by_query(self, query: str) -> List[SearchHistoryEntry]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM search_history
            WHERE query LIKE ?
            ORDER BY searched_at DESC
            """,
            (f"%{query}%",),
        )

        return [self._row_to_entry(row) for row in cursor.fetchall()]
