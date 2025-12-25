
import logging
import os
import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from weakref import WeakValueDictionary

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..domain.value_objects.search_query import SearchMode
from ..infrastructure.container import (
    Container,
    ContainerConfig,
    PersistenceConfig,
    VectorConfig,
)

logger = logging.getLogger(__name__)


class FileLockManager:

    def __init__(self, max_locks: int = 1000) -> None:
        self._locks: WeakValueDictionary[str, threading.RLock] = WeakValueDictionary()
        self._global_lock = threading.Lock()
        self._active_locks: Dict[str, threading.RLock] = {}
        self._max_locks = max_locks

    def acquire(self, path: str) -> threading.RLock:
        with self._global_lock:
            if path not in self._active_locks:
                if len(self._active_locks) >= self._max_locks:
                    oldest_key = next(iter(self._active_locks))
                    del self._active_locks[oldest_key]
                self._active_locks[path] = threading.RLock()
            lock = self._active_locks[path]

        lock.acquire()
        return lock

    def release(self, path: str, lock: threading.RLock) -> None:
        lock.release()

    def __call__(self, path: str):
        return _FileLockContext(self, path)


class _FileLockContext:

    def __init__(self, manager: FileLockManager, path: str) -> None:
        self._manager = manager
        self._path = path
        self._lock: Optional[threading.RLock] = None

    def __enter__(self) -> threading.RLock:
        self._lock = self._manager.acquire(self._path)
        return self._lock

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._lock:
            self._manager.release(self._path, self._lock)
        return False

__all__ = ["ApplicationService", "SearchMode", "SearchResult", "FolderSettings"]

@dataclass
class SearchResult:

    file_path: str
    similarity_score: float
    match_type: str
    chunk_index: Optional[int] = None
    snippet: str = ""

@dataclass
class FolderSettings:

    include_hidden: bool = False
    index_content: bool = True

class FileChangeHandler(FileSystemEventHandler):

    SUPPORTED_EXTENSIONS = (
        ".txt", ".md", ".py", ".json", ".csv", ".pdf",
        ".png", ".jpg", ".jpeg", ".webp"
    )

    def __init__(
        self,
        app_service: "ApplicationService",
        folder_settings: Dict[str, FolderSettings],
    ) -> None:
        self._app_service = app_service
        self._folder_settings = folder_settings

    def _should_process(self, file_path: str) -> bool:
        if not file_path.lower().endswith(self.SUPPORTED_EXTENSIONS):
            return False

        for folder, settings in self._folder_settings.items():
            if file_path.startswith(folder):
                if not settings.include_hidden and self._is_hidden(file_path):
                    return False
                return True

        return True

    def _is_hidden(self, file_path: str) -> bool:
        parts = file_path.split(os.sep)
        return any(part.startswith(".") for part in parts if part)

    def on_created(self, event) -> None:
        if not event.is_directory:
            if self._should_process(event.src_path):
                logger.debug("File created: %s", event.src_path)
                self._app_service.index_file(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            if self._should_process(event.src_path):
                logger.debug("File modified: %s", event.src_path)
                self._app_service.remove_file(event.src_path)
                self._app_service.index_file(event.src_path)

    def on_deleted(self, event) -> None:
        if not event.is_directory:
            logger.debug("File deleted: %s", event.src_path)
            self._app_service.remove_file(event.src_path)

class ApplicationService:

    SUPPORTED_EXTENSIONS = (
        ".txt", ".md", ".py", ".json", ".csv", ".pdf",
        ".png", ".jpg", ".jpeg", ".webp"
    )

    def __init__(
        self,
        metadata_db_path: str = "./metadata.db",
        vector_db_path: str = "./milvus_lite.db",
    ) -> None:
        self._container = Container(
            ContainerConfig(
                persistence=PersistenceConfig(db_path=metadata_db_path),
                vector=VectorConfig(db_path=vector_db_path),
            )
        )

        self._folder_settings: Dict[str, FolderSettings] = {}

        self._observer: Optional[Observer] = None
        self._watch_dirs: List[str] = []

        self._file_lock_manager = FileLockManager()

    @property
    def watch_dirs(self) -> List[str]:
        return self._watch_dirs

    @property
    def observer(self) -> Observer:
        if self._observer is None:
            self._observer = Observer()
        return self._observer

    def set_folder_settings(
        self,
        folder: str,
        include_hidden: bool = False,
        index_content: bool = True,
    ) -> None:
        self._folder_settings[folder] = FolderSettings(
            include_hidden=include_hidden,
            index_content=index_content,
        )

    def get_folder_settings(self, folder: str) -> FolderSettings:
        return self._folder_settings.get(folder, FolderSettings())

    def should_include_file(self, file_path: str) -> bool:
        if not file_path.lower().endswith(self.SUPPORTED_EXTENSIONS):
            return False

        for folder, settings in self._folder_settings.items():
            if file_path.startswith(folder):
                if not settings.include_hidden and self._is_hidden(file_path):
                    return False
                return True

        return not self._is_hidden(file_path)

    def should_index_content(self, file_path: str) -> bool:
        for folder, settings in self._folder_settings.items():
            if file_path.startswith(folder):
                return settings.index_content
        return True

    def _is_hidden(self, file_path: str) -> bool:
        parts = file_path.split(os.sep)
        return any(part.startswith(".") for part in parts if part)

    def collect_files(self, folder: str) -> List[str]:
        files = []
        settings = self.get_folder_settings(folder)

        for root, dirs, filenames in os.walk(folder):
            if not settings.include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in filenames:
                if filename.lower().endswith(self.SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, filename)

                    if not settings.include_hidden and self._is_hidden(file_path):
                        continue

                    files.append(file_path)

        return files

    def index_file(
        self,
        file_path: str,
        index_content: bool = True,
    ) -> bool:
        with self._file_lock_manager(file_path):
            result = self._container.index_file_use_case.execute(
                file_path=file_path,
                index_content=index_content,
            )
            return result.success

    def index_filename(self, file_path: str) -> bool:
        return self.index_file(file_path, index_content=False)

    def index_content(self, file_path: str) -> bool:
        return self.index_file(file_path, index_content=True)

    def index_folder(
        self,
        folder: str,
        include_hidden: bool = False,
        index_content: bool = True,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        self.set_folder_settings(folder, include_hidden, index_content)

        result = self._container.index_folder_use_case.execute(
            folder_path=folder,
            include_hidden=include_hidden,
            index_content=index_content,
            progress_callback=progress_callback,
        )

        return result.indexed_files, result.total_files

    def remove_file(self, file_path: str) -> bool:
        with self._file_lock_manager(file_path):
            try:
                existing = self._container.file_repository.find_by_path(file_path)
                if existing and existing.id is not None:
                    self._container.chunk_repository.delete_by_file_id(existing.id)

                    from ..domain.constants import CONTENT_COLLECTION, FILENAME_COLLECTION

                    vector_ids = self._container.chunk_repository.get_vector_ids_for_file(
                        existing.id
                    )
                    if vector_ids:
                        self._container.vector_store.delete(CONTENT_COLLECTION, vector_ids)

                    self._container.vector_store.delete(FILENAME_COLLECTION, [file_path])

                    self._container.keyword_search.delete_by_file_path(file_path)

                    self._container.file_repository.delete(existing.id)

                return True

            except Exception as err:
                logger.error("Failed to remove file %s: %s", file_path, err)
                return False

    def search(
        self,
        query: str,
        n_results: int = 20,
        mode: SearchMode = SearchMode.FILENAME,
        offset: int = 0,
    ) -> Tuple[List[SearchResult], bool]:
        response = self._container.search_use_case.execute(
            query=query,
            mode=mode,
            top_k=n_results,
            offset=offset,
        )

        results = [
            SearchResult(
                file_path=r.file_path,
                similarity_score=r.similarity_score,
                match_type=r.match_type,
                chunk_index=r.chunk_index,
                snippet=r.snippet,
            )
            for r in response.results
        ]
        return results, response.has_more

    def invalidate_search_cache(self) -> None:
        pass

    def start_watching(self, folder: str) -> None:
        if folder in self._watch_dirs:
            return

        event_handler = FileChangeHandler(self, self._folder_settings)
        self.observer.schedule(event_handler, folder, recursive=True)

        if not self.observer.is_alive():
            self.observer.start()

        self._watch_dirs.append(folder)
        logger.info("Started watching: %s", folder)

    def stop_watching(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        self._watch_dirs.clear()
        logger.info("Stopped all file watchers")

    def close(self) -> None:
        self.stop_watching()
        self._container.close()
        logger.info("ApplicationService closed")

    def __enter__(self) -> "ApplicationService":
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        self.close()
        return False
