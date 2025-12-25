
import logging
import re
from typing import List, Optional

from ....domain.ports.keyword_search_port import KeywordSearchHit, KeywordSearchPort
from .connection import SqliteConnectionManager

logger = logging.getLogger(__name__)

FTS_SCHEMA_SQL = """
-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    doc_id,
    content,
    file_path,
    chunk_index,
    tokenize='porter unicode61 remove_diacritics 1'
);
"""

class SqliteFTS5Adapter(KeywordSearchPort):

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._conn_manager = connection_manager
        self._initialize_fts()

    def _initialize_fts(self) -> None:
        conn = self._conn_manager.get_connection()
        try:
            conn.executescript(FTS_SCHEMA_SQL)
            conn.commit()
            logger.info("FTS5 virtual table initialized")
        except Exception as err:
            logger.error("Failed to initialize FTS5: %s", err)
            raise

    def _sanitize_query(self, query: str) -> str:
        sanitized = re.sub(r'[^\w\s가-힣]', ' ', query)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()

        if not sanitized:
            return '""'

        words = sanitized.split()
        if len(words) == 1:
            return f'"{words[0]}"*'

        return ' '.join(f'"{w}"*' for w in words)

    def index_content(
        self,
        doc_id: str,
        content: str,
        file_path: str,
        chunk_index: Optional[int] = None,
    ) -> bool:
        try:
            with self._conn_manager.transaction() as conn:
                conn.execute(
                    "DELETE FROM content_fts WHERE doc_id = ?",
                    (doc_id,),
                )

                conn.execute(
                    """
                    INSERT INTO content_fts (doc_id, content, file_path, chunk_index)
                    VALUES (?, ?, ?, ?)
                    """,
                    (doc_id, content, file_path, str(chunk_index) if chunk_index is not None else ""),
                )

            return True

        except Exception as err:
            logger.error("Failed to index content in FTS: %s", err)
            return False

    def index_batch(
        self,
        documents: List[tuple],
    ) -> int:
        if not documents:
            return 0

        try:
            with self._conn_manager.transaction() as conn:
                doc_ids = [d[0] for d in documents]
                placeholders = ",".join("?" * len(doc_ids))
                conn.execute(
                    f"DELETE FROM content_fts WHERE doc_id IN ({placeholders})",
                    doc_ids,
                )

                conn.executemany(
                    """
                    INSERT INTO content_fts (doc_id, content, file_path, chunk_index)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (d[0], d[1], d[2], str(d[3]) if d[3] is not None else "")
                        for d in documents
                    ],
                )

            return len(documents)

        except Exception as err:
            logger.error("Failed to batch index in FTS: %s", err)
            return 0

    def search(
        self,
        query: str,
        top_k: int = 20,
        offset: int = 0,
    ) -> List[KeywordSearchHit]:
        if not query or not query.strip():
            return []

        sanitized_query = self._sanitize_query(query)
        if not sanitized_query or sanitized_query == '""':
            return []

        try:
            conn = self._conn_manager.get_connection()

            cursor = conn.execute(
                """
                SELECT
                    doc_id,
                    -bm25(content_fts) as score,
                    file_path,
                    chunk_index,
                    snippet(content_fts, 1, '<mark>', '</mark>', '...', 64) as snippet
                FROM content_fts
                WHERE content_fts MATCH ?
                ORDER BY score DESC
                LIMIT ? OFFSET ?
                """,
                (sanitized_query, top_k, offset),
            )

            results = []
            for row in cursor.fetchall():
                chunk_idx = None
                if row["chunk_index"] and row["chunk_index"] != "":
                    try:
                        chunk_idx = int(row["chunk_index"])
                    except ValueError:
                        pass

                results.append(
                    KeywordSearchHit(
                        id=row["doc_id"],
                        score=float(row["score"]),
                        file_path=row["file_path"],
                        chunk_index=chunk_idx,
                        snippet=row["snippet"] or "",
                    )
                )

            return results

        except Exception as err:
            logger.error("FTS5 search error: %s (query: %s)", err, sanitized_query)
            return []

    def delete_by_file_path(self, file_path: str) -> int:
        try:
            with self._conn_manager.transaction() as conn:
                cursor = conn.execute(
                    "DELETE FROM content_fts WHERE file_path = ?",
                    (file_path,),
                )
                return cursor.rowcount

        except Exception as err:
            logger.error("Failed to delete FTS content: %s", err)
            return 0

    def delete_by_doc_id(self, doc_id: str) -> bool:
        try:
            with self._conn_manager.transaction() as conn:
                cursor = conn.execute(
                    "DELETE FROM content_fts WHERE doc_id = ?",
                    (doc_id,),
                )
                return cursor.rowcount > 0

        except Exception as err:
            logger.error("Failed to delete FTS document: %s", err)
            return False

    def count(self) -> int:
        try:
            conn = self._conn_manager.get_connection()
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM content_fts")
            return cursor.fetchone()["cnt"]

        except Exception as err:
            logger.error("Failed to count FTS documents: %s", err)
            return 0

    def optimize(self) -> bool:
        try:
            conn = self._conn_manager.get_connection()
            conn.execute("INSERT INTO content_fts(content_fts) VALUES('optimize')")
            conn.commit()
            logger.info("FTS5 index optimized")
            return True

        except Exception as err:
            logger.error("Failed to optimize FTS5: %s", err)
            return False
