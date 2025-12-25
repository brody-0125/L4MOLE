
import logging
from typing import List, Optional

from ....domain.entities.chunk_entity import ChunkEntity
from ....domain.ports.chunk_repository import ChunkRepository
from ....domain.ports.text_compressor_port import CompressionType
from ....domain.value_objects.content_hash import ContentHash
from .connection import SqliteConnectionManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Content chunks with compression
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    vector_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    compressed_content BLOB,
    original_size INTEGER NOT NULL DEFAULT 0,
    compressed_size INTEGER NOT NULL DEFAULT 0,
    compression_type TEXT DEFAULT 'none',
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    UNIQUE(file_id, chunk_index),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Indexes for chunk lookups
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_vector ON chunks(vector_id);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);
"""

class SqliteChunkRepository(ChunkRepository):

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._conn_manager = connection_manager
        self._conn_manager.initialize_schema(SCHEMA_SQL)

    def _row_to_entity(self, row) -> ChunkEntity:
        return ChunkEntity(
            id=row["id"],
            file_id=row["file_id"],
            chunk_index=row["chunk_index"],
            vector_id=row["vector_id"],
            content_hash=ContentHash(value=row["content_hash"]),
            compressed_content=row["compressed_content"],
            original_size=row["original_size"],
            compressed_size=row["compressed_size"],
            compression_type=CompressionType(row["compression_type"]),
        )

    def save(self, entity: ChunkEntity) -> ChunkEntity:
        with self._conn_manager.transaction() as conn:
            if entity.id is not None:
                conn.execute(
                    """
                    UPDATE chunks SET
                        file_id = ?,
                        chunk_index = ?,
                        vector_id = ?,
                        content_hash = ?,
                        compressed_content = ?,
                        original_size = ?,
                        compressed_size = ?,
                        compression_type = ?
                    WHERE id = ?
                    """,
                    (
                        entity.file_id,
                        entity.chunk_index,
                        entity.vector_id,
                        entity.content_hash.value,
                        entity.compressed_content,
                        entity.original_size,
                        entity.compressed_size,
                        entity.compression_type.value,
                        entity.id,
                    ),
                )
                return entity

            cursor = conn.execute(
                """
                INSERT INTO chunks (
                    file_id, chunk_index, vector_id, content_hash,
                    compressed_content, original_size, compressed_size,
                    compression_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, chunk_index) DO UPDATE SET
                    vector_id = excluded.vector_id,
                    content_hash = excluded.content_hash,
                    compressed_content = excluded.compressed_content,
                    original_size = excluded.original_size,
                    compressed_size = excluded.compressed_size,
                    compression_type = excluded.compression_type
                """,
                (
                    entity.file_id,
                    entity.chunk_index,
                    entity.vector_id,
                    entity.content_hash.value,
                    entity.compressed_content,
                    entity.original_size,
                    entity.compressed_size,
                    entity.compression_type.value,
                ),
            )

            entity.id = cursor.lastrowid
            return entity

    def save_batch(self, entities: List[ChunkEntity]) -> List[ChunkEntity]:
        if not entities:
            return []

        with self._conn_manager.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO chunks (
                    file_id, chunk_index, vector_id, content_hash,
                    compressed_content, original_size, compressed_size,
                    compression_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id, chunk_index) DO UPDATE SET
                    vector_id = excluded.vector_id,
                    content_hash = excluded.content_hash,
                    compressed_content = excluded.compressed_content,
                    original_size = excluded.original_size,
                    compressed_size = excluded.compressed_size,
                    compression_type = excluded.compression_type
                """,
                [
                    (
                        e.file_id,
                        e.chunk_index,
                        e.vector_id,
                        e.content_hash.value,
                        e.compressed_content,
                        e.original_size,
                        e.compressed_size,
                        e.compression_type.value,
                    )
                    for e in entities
                ],
            )
            return entities

    def find_by_id(self, chunk_id: int) -> Optional[ChunkEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM chunks WHERE id = ?",
            (chunk_id,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_by_file_id(self, file_id: int) -> List[ChunkEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM chunks WHERE file_id = ? ORDER BY chunk_index",
            (file_id,),
        )

        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_by_vector_id(self, vector_id: str) -> Optional[ChunkEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM chunks WHERE vector_id = ?",
            (vector_id,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_by_hash(self, content_hash: ContentHash) -> Optional[ChunkEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM chunks WHERE content_hash = ? LIMIT 1",
            (content_hash.value,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def delete_by_file_id(self, file_id: int) -> int:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM chunks WHERE file_id = ?",
                (file_id,),
            )
            return cursor.rowcount

    def delete_by_vector_ids(self, vector_ids: List[str]) -> int:
        if not vector_ids:
            return 0

        placeholders = ",".join("?" * len(vector_ids))
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM chunks WHERE vector_id IN ({placeholders})",
                vector_ids,
            )
            return cursor.rowcount

    def count(self) -> int:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM chunks")
        return cursor.fetchone()["cnt"]

    def count_by_file_id(self, file_id: int) -> int:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE file_id = ?",
            (file_id,),
        )
        return cursor.fetchone()["cnt"]

    def get_vector_ids_for_file(self, file_id: int) -> List[str]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT vector_id FROM chunks WHERE file_id = ?",
            (file_id,),
        )
        return [row["vector_id"] for row in cursor.fetchall()]

    def get_compression_stats(self) -> dict:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as chunk_count,
                COALESCE(SUM(original_size), 0) as total_original_size,
                COALESCE(SUM(compressed_size), 0) as total_compressed_size
            FROM chunks
            """
        )
        row = cursor.fetchone()

        total_original = row["total_original_size"]
        total_compressed = row["total_compressed_size"]

        compression_ratio = 0.0
        if total_original > 0:
            compression_ratio = 1.0 - (total_compressed / total_original)

        return {
            "chunk_count": row["chunk_count"],
            "total_original_size": total_original,
            "total_compressed_size": total_compressed,
            "compression_ratio": compression_ratio,
            "space_saved": total_original - total_compressed,
        }
