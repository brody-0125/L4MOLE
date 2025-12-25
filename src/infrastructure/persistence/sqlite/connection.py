
import logging
import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, List

logger = logging.getLogger(__name__)

class SqliteConnectionManager:

    PRAGMA_SETTINGS: List[str] = [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=5000",
        "PRAGMA cache_size=-65536",
        "PRAGMA mmap_size=268435456",
        "PRAGMA temp_store=MEMORY",
        "PRAGMA foreign_keys=ON",
    ]

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._initialized = False

    @property
    def db_path(self) -> str:
        return self._db_path

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.conn.row_factory = sqlite3.Row

            for pragma in self.PRAGMA_SETTINGS:
                self._local.conn.execute(pragma)

            logger.debug("Created new SQLite connection for thread")

        return self._local.conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def initialize_schema(self, schema_sql: str) -> None:
        with self.transaction() as conn:
            conn.executescript(schema_sql)
            if not self._initialized:
                self._initialized = True
                logger.info("Database schema initialized")

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as err:
                logger.warning("Error closing connection: %s", err)
            finally:
                self._local.conn = None

    def __enter__(self) -> "SqliteConnectionManager":
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        self.close()
        return False
