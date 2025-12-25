
import logging
from typing import List, Optional

from ....domain.entities.folder_entity import FolderEntity, FolderSettings
from ....domain.ports.folder_repository import FolderRepository
from .connection import SqliteConnectionManager

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- Indexed folders configuration
CREATE TABLE IF NOT EXISTS indexed_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    include_hidden INTEGER DEFAULT 0,
    index_content INTEGER DEFAULT 1,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_folders_path ON indexed_folders(path);
"""

class SqliteFolderRepository(FolderRepository):

    def __init__(self, connection_manager: SqliteConnectionManager) -> None:
        self._conn_manager = connection_manager
        self._conn_manager.initialize_schema(SCHEMA_SQL)

    def _row_to_entity(self, row) -> FolderEntity:
        settings = FolderSettings(
            include_hidden=bool(row["include_hidden"]),
            index_content=bool(row["index_content"]),
        )

        return FolderEntity(
            id=row["id"],
            path=row["path"],
            settings=settings,
        )

    def save(self, entity: FolderEntity) -> FolderEntity:
        with self._conn_manager.transaction() as conn:
            if entity.id is not None:
                conn.execute(
                    """
                    UPDATE indexed_folders SET
                        path = ?,
                        include_hidden = ?,
                        index_content = ?,
                        updated_at = strftime('%s', 'now')
                    WHERE id = ?
                    """,
                    (
                        entity.path,
                        int(entity.settings.include_hidden),
                        int(entity.settings.index_content),
                        entity.id,
                    ),
                )
                return entity

            cursor = conn.execute(
                """
                INSERT INTO indexed_folders (
                    path, include_hidden, index_content
                ) VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    include_hidden = excluded.include_hidden,
                    index_content = excluded.index_content,
                    updated_at = strftime('%s', 'now')
                """,
                (
                    entity.path,
                    int(entity.settings.include_hidden),
                    int(entity.settings.index_content),
                ),
            )

            entity.id = cursor.lastrowid
            return entity

    def find_by_id(self, folder_id: int) -> Optional[FolderEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM indexed_folders WHERE id = ?",
            (folder_id,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_by_path(self, path: str) -> Optional[FolderEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM indexed_folders WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()

        if row:
            return self._row_to_entity(row)
        return None

    def find_all(self) -> List[FolderEntity]:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT * FROM indexed_folders ORDER BY path"
        )

        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def delete(self, path: str) -> bool:
        with self._conn_manager.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM indexed_folders WHERE path = ?",
                (path,),
            )
            return cursor.rowcount > 0

    def exists(self, path: str) -> bool:
        conn = self._conn_manager.get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM indexed_folders WHERE path = ? LIMIT 1",
            (path,),
        )
        return cursor.fetchone() is not None
