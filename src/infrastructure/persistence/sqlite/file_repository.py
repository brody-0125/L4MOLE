
import logging
import os
from typing import List, Optional

from ....domain.entities.file_entity import FileEntity, IndexStatus
from ....domain.ports.file_repository import FileRepository
from ....domain.value_objects.content_hash import ContentHash
from ....domain.value_objects.file_path import FilePath
from ....domain.value_objects.file_type import FileType
from .connection import SqliteConnectionManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Directory dictionary for path compression
CREATE TABLE IF NOT EXISTS directories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Main files table
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory_id INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    mtime INTEGER NOT NULL,
    content_hash TEXT,
    chunk_count INTEGER DEFAULT 0,
    index_status TEXT DEFAULT 'pending',
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (directory_id) REFERENCES directories(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_directory ON files(directory_id);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(index_status);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_type ON files(file_type);
CREATE INDEX IF NOT EXISTS idx_directories_path ON directories(path);
"""

class SqliteFileRepository(FileRepository):

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._conn_manager = connection_manager
        self._conn_manager.initialize_schema(SCHEMA_SQL)

    def _get_or_create_directory(self, directory: str) -> int:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                "SELECT id FROM directories WHERE path = ?",
                (directory,),
            )
            row = cursor.fetchone()

            if row:
                return row["id"]

            cursor = conn.execute(
                "INSERT INTO directories (path) VALUES (?)",
                (directory,),
            )
            return cursor.lastrowid

    def _row_to_entity(self, row) -> FileEntity:
        content_hash = None
        if row["content_hash"]:
            content_hash = ContentHash(value=row["content_hash"])

        return FileEntity(
            id=row["id"],
            path=FilePath(path=row["path"]),
            file_type=FileType.from_path(row["path"]),
            size=row["size"],
            mtime=row["mtime"],
            content_hash=content_hash,
            chunk_count=row["chunk_count"],
            status=IndexStatus(row["index_status"]),
        )

    def save(self, entity: FileEntity) -> FileEntity:
        directory = entity.path.directory
        directory_id = self._get_or_create_directory(directory)

        content_hash_value = None
        if entity.content_hash:
            content_hash_value = entity.content_hash.value

        with self._conn_manager.transaction() as conn:
            if entity.id is not None:
                conn.execute(
                    """
                    UPDATE files SET
                        filename = ?,
                        directory_id = ?,
                        file_type = ?,
                        size = ?,
                        mtime = ?,
                        content_hash = ?,
                        chunk_count = ?,
                        index_status = ?,
                        updated_at = strftime('%s', 'now')
                    WHERE id = ?
                    """,
                    (
                        entity.path.filename,
                        directory_id,
                        entity.file_type.category.value,
                        entity.size,
                        entity.mtime,
                        content_hash_value,
                        entity.chunk_count,
                        entity.status.value,
                        entity.id,
                    ),
                )
                return entity

            cursor = conn.execute(
                """
                INSERT INTO files (
                    path, filename, directory_id, file_type,
                    size, mtime, content_hash, chunk_count, index_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    filename = excluded.filename,
                    directory_id = excluded.directory_id,
                    file_type = excluded.file_type,
                    size = excluded.size,
                    mtime = excluded.mtime,
                    content_hash = excluded.content_hash,
                    chunk_count = excluded.chunk_count,
                    index_status = excluded.index_status,
                    updated_at = strftime('%s', 'now')
                """,
                (
                    entity.path.path,
                    entity.path.filename,
                    directory_id,
                    entity.file_type.category.value,
                    entity.size,
                    entity.mtime,
                    content_hash_value,
                    entity.chunk_count,
                    entity.status.value,
                ),
            )

            entity.id = cursor.lastrowid
            return entity

    def find_by_id(self, file_id: int) -> Optional[FileEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM files WHERE id = ?",
            (file_id,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_by_path(self, path: str) -> Optional[FileEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM files WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_by_directory(self, directory: str) -> List[FileEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            """
            SELECT f.* FROM files f
            JOIN directories d ON f.directory_id = d.id
            WHERE d.path = ?
            """,
            (directory,),
        )

        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_by_status(
        self,
        status: IndexStatus,
        limit: int = 1000,
    ) -> List[FileEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM files WHERE index_status = ? LIMIT ?",
            (status.value, limit),
        )

        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_changed(self, path: str, mtime: int) -> bool:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT mtime FROM files WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()

        if row is None:
            return True

        return row["mtime"] != mtime

    def delete(self, path: str) -> bool:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM files WHERE path = ?",
                (path,),
            )
            return cursor.rowcount > 0

    def delete_by_id(self, file_id: int) -> bool:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM files WHERE id = ?",
                (file_id,),
            )
            return cursor.rowcount > 0

    def delete_by_directory(self, directory: str) -> int:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                """
                DELETE FROM files WHERE directory_id IN (
                    SELECT id FROM directories WHERE path = ?
                )
                """,
                (directory,),
            )
            return cursor.rowcount

    def count(self) -> int:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM files")
        return cursor.fetchone()["cnt"]

    def count_by_status(self, status: IndexStatus) -> int:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM files WHERE index_status = ?",
            (status.value,),
        )
        return cursor.fetchone()["cnt"]

    def exists(self, path: str) -> bool:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM files WHERE path = ? LIMIT 1",
            (path,),
        )
        return cursor.fetchone() is not None
