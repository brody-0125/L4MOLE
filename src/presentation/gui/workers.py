
import os
from typing import Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ..app_service import ApplicationService
from ...domain.value_objects.search_query import SearchMode


class FilenameIndexingWorker(QThread):
    """
    Worker thread for indexing filenames.

    Uses an injected ApplicationService singleton instead of creating
    a new instance each time.
    """

    finished = pyqtSignal()
    cancelled = pyqtSignal()
    progress = pyqtSignal(str)
    file_progress = pyqtSignal(int, int)

    def __init__(
        self,
        folders: List[str],
        folder_settings: Optional[Dict[str, Dict]] = None,
        app_service: Optional[ApplicationService] = None,
    ) -> None:
        super().__init__()
        self._folders = folders
        self._folder_settings = folder_settings or {}
        self._app_service = app_service
        self._owns_app_service = False
        self._is_cancelled = False
        self._files: List[str] = []

    def cancel(self) -> None:
        self._is_cancelled = True
        self.progress.emit("Cancelling filename indexing...")

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def get_files(self) -> List[str]:
        return self._files

    def get_app_service(self) -> Optional[ApplicationService]:
        return self._app_service

    def get_folder_settings(self) -> Dict[str, Dict]:
        return self._folder_settings

    def run(self) -> None:
        try:
            if self._app_service is None:
                from ...infrastructure.di import AppInjector
                self._app_service = AppInjector.get_instance().get_app_service()

            self._files = []

            for folder, settings in self._folder_settings.items():
                self._app_service.set_folder_settings(
                    folder,
                    include_hidden=settings.get("include_hidden", False),
                    index_content=settings.get("index_content", True)
                )

            for folder in self._folders:
                if self._is_cancelled:
                    break
                self._files.extend(self._app_service.collect_files(folder))

            if self._is_cancelled:
                self.cancelled.emit()
                return

            total_files = len(self._files)
            self.progress.emit(f"File scan complete: {total_files} files found")
            self.file_progress.emit(0, total_files)

            for idx, file_path in enumerate(self._files):
                if self._is_cancelled:
                    break

                filename = os.path.basename(file_path)
                self.progress.emit(f"[{idx + 1}/{total_files}] Indexing filename: {filename}")
                self.file_progress.emit(idx + 1, total_files)
                self._app_service.index_filename(file_path)

            for folder in self._folders:
                if self._is_cancelled:
                    break
                if folder not in self._app_service.watch_dirs:
                    self._app_service.start_watching(folder)

            if self._is_cancelled:
                self.progress.emit("Filename indexing cancelled")
                self.cancelled.emit()
            else:
                self.progress.emit(f"Filename indexing complete: {total_files} files")
                self._flush_vector_store()
                self.finished.emit()

        except Exception as err:
            self.progress.emit(f"Filename indexing error: {err}")
            self.finished.emit()

    def _flush_vector_store(self) -> None:
        """Flush vector store to ensure data is persisted."""
        if self._app_service is not None:
            try:
                self._app_service._container.vector.vector_store.close()
                self._app_service._container._vector = None
            except Exception:
                pass

    def cleanup(self) -> None:
        """
        Cleanup worker resources.

        Note: Does NOT close the ApplicationService since it's a shared singleton.
        """
        pass


class ContentIndexingWorker(QThread):
    """
    Worker thread for indexing file contents.

    Uses an injected ApplicationService singleton instead of creating
    a new instance each time.
    """

    finished = pyqtSignal()
    cancelled = pyqtSignal()
    progress = pyqtSignal(str)
    file_progress = pyqtSignal(int, int)

    def __init__(
        self,
        files: List[str],
        app_service: Optional[ApplicationService] = None
    ) -> None:
        super().__init__()
        self._files = files
        self._app_service = app_service
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True
        self.progress.emit("Cancelling content indexing...")

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        try:
            if self._app_service is None:
                from ...infrastructure.di import AppInjector
                self._app_service = AppInjector.get_instance().get_app_service()

            files_to_index = [
                f for f in self._files
                if self._app_service.should_index_content(f)
            ]
            skipped_count = len(self._files) - len(files_to_index)

            if skipped_count > 0:
                self.progress.emit(
                    f"Content indexing target: {len(files_to_index)} files "
                    f"({skipped_count} excluded by settings)"
                )

            total_files = len(files_to_index)
            self.file_progress.emit(0, total_files)

            indexed_count = 0
            for idx, file_path in enumerate(files_to_index):
                if self._is_cancelled:
                    break

                filename = os.path.basename(file_path)
                self.progress.emit(f"[{idx + 1}/{total_files}] Indexing content: {filename}")
                self.file_progress.emit(idx + 1, total_files)
                self._app_service.index_content(file_path)
                indexed_count = idx + 1

            if self._is_cancelled:
                self.progress.emit(f"Content indexing cancelled: {indexed_count}/{total_files} completed")
                self.cancelled.emit()
            else:
                msg = f"Content indexing complete: {total_files} files"
                if skipped_count > 0:
                    msg += f" ({skipped_count} excluded by settings)"
                self.progress.emit(msg)
                self.finished.emit()

        except Exception as err:
            self.progress.emit(f"Content indexing error: {err}")
            self.finished.emit()

        finally:
            self._flush_vector_store()

    def _flush_vector_store(self) -> None:
        """Flush vector store to ensure data is persisted."""
        if self._app_service is not None:
            try:
                self._app_service._container.vector.vector_store.close()
                self._app_service._container._vector = None
            except Exception:
                pass


class SearchWorker(QThread):
    """
    Worker thread for performing searches.

    Uses an injected ApplicationService singleton instead of creating
    a new instance each time.
    """

    results_ready = pyqtSignal(list, bool)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        query: str,
        n_results: int = 10,
        mode: SearchMode = SearchMode.FILENAME,
        app_service: Optional[ApplicationService] = None,
        offset: int = 0,
    ) -> None:
        super().__init__()
        self._query = query
        self._n_results = n_results
        self._mode = mode
        self._app_service = app_service
        self._offset = offset

    def run(self) -> None:
        try:
            if self._app_service is None:
                from ...infrastructure.di import AppInjector
                self._app_service = AppInjector.get_instance().get_app_service()

            results, has_more = self._app_service.search(
                self._query,
                n_results=self._n_results,
                mode=self._mode,
                offset=self._offset,
            )
            result_dicts = []
            for r in results:
                distance = 2 * (1 - r.similarity_score / 100)
                result_dicts.append({
                    "path": r.file_path,
                    "distance": distance,
                    "type": r.match_type,
                    "chunk_index": r.chunk_index,
                    "snippet": r.snippet or "",
                })
            self.results_ready.emit(result_dicts, has_more)
        except Exception as err:
            error_msg = str(err)
            if "collection not found" in error_msg.lower():
                error_msg = "No indexed data found. Please add folders and run indexing first."
            elif "connection" in error_msg.lower():
                error_msg = "Failed to connect to search service. Please try again."
            self.error_occurred.emit(error_msg)
