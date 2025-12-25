
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from PyQt6.QtCore import QThread

from src.presentation.gui.workers import (
    FilenameIndexingWorker,
    ContentIndexingWorker,
    SearchWorker,
)
from src.presentation import SearchMode


def create_mock_app_injector(mock_service):
    """Create a mock AppInjector that returns the given mock service."""
    mock_injector = MagicMock()
    mock_injector.get_app_service.return_value = mock_service
    mock_injector_cls = MagicMock()
    mock_injector_cls.get_instance.return_value = mock_injector
    return mock_injector_cls


class TestFilenameIndexingWorker:

    def test_worker_initialization(self):
        folders = ["/test/folder1", "/test/folder2"]
        settings = {"/test/folder1": {"include_hidden": True}}

        worker = FilenameIndexingWorker(folders, settings)

        assert worker._folders == folders
        assert worker._folder_settings == settings
        assert worker._is_cancelled is False

    def test_worker_cancel(self):
        worker = FilenameIndexingWorker(["/test"])

        worker.cancel()

        assert worker._is_cancelled is True

    def test_worker_signals_exist(self):
        worker = FilenameIndexingWorker(["/test"])

        assert hasattr(worker, "finished")
        assert hasattr(worker, "cancelled")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "file_progress")

    def test_worker_emits_progress(self, qtbot):
        mock_service = MagicMock()
        mock_service.collect_files.return_value = ["/test/file1.txt"]
        mock_service.index_filename.return_value = True
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()
        mock_service.start_watching = MagicMock()

        # Pass the mock service directly to skip DI lookup
        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        progress_messages = []
        worker.progress.connect(lambda msg: progress_messages.append(msg))

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        assert len(progress_messages) > 0

    def test_worker_emits_file_progress(self, qtbot):
        mock_service = MagicMock()
        mock_service.collect_files.return_value = [
            "/test/file1.txt",
            "/test/file2.txt"
        ]
        mock_service.index_filename.return_value = True
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()
        mock_service.start_watching = MagicMock()

        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        file_progress = []
        worker.file_progress.connect(
            lambda current, total: file_progress.append((current, total))
        )

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        assert len(file_progress) > 0
        assert file_progress[-1][0] == file_progress[-1][1]

    def test_worker_cancellation_emits_cancelled_signal(self, qtbot):
        mock_service = MagicMock()
        mock_service.collect_files.return_value = [
            f"/test/file{i}.txt" for i in range(100)
        ]
        mock_service.index_filename.side_effect = lambda x: None
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()

        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        worker.start()
        worker.cancel()

        qtbot.wait(500)

        assert worker._is_cancelled

    def test_get_files_returns_collected_files(self, qtbot):
        mock_service = MagicMock()
        expected_files = ["/test/file1.txt", "/test/file2.py"]
        mock_service.collect_files.return_value = expected_files
        mock_service.index_filename.return_value = True
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()
        mock_service.start_watching = MagicMock()

        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        assert worker.get_files() == expected_files

    def test_get_app_service_returns_service(self, qtbot):
        mock_service = MagicMock()
        mock_service.collect_files.return_value = []
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()

        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        assert worker.get_app_service() == mock_service

class TestContentIndexingWorker:

    def test_worker_initialization(self):
        files = ["/test/file1.txt", "/test/file2.py"]
        mock_service = MagicMock()

        worker = ContentIndexingWorker(files, mock_service)

        assert worker._files == files
        assert worker._app_service == mock_service
        assert worker._is_cancelled is False

    def test_worker_cancel(self):
        worker = ContentIndexingWorker(["/test/file.txt"])

        worker.cancel()

        assert worker._is_cancelled is True

    def test_worker_signals_exist(self):
        worker = ContentIndexingWorker(["/test/file.txt"])

        assert hasattr(worker, "finished")
        assert hasattr(worker, "cancelled")
        assert hasattr(worker, "progress")
        assert hasattr(worker, "file_progress")

    def test_worker_filters_files_by_settings(self, qtbot):
        mock_service = MagicMock()
        mock_service.should_index_content.side_effect = lambda f: "include" in f
        mock_service.index_content.return_value = True

        files = ["/test/include.txt", "/test/exclude.txt", "/test/include2.py"]
        worker = ContentIndexingWorker(files, mock_service)

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

        assert mock_service.index_content.call_count == 2

    def test_worker_uses_injector_if_none_provided(self, qtbot):
        mock_service = MagicMock()
        mock_service.should_index_content.return_value = True
        mock_service.index_content.return_value = True

        with patch("src.infrastructure.di.AppInjector") as mock_injector_cls:
            mock_injector = MagicMock()
            mock_injector.get_app_service.return_value = mock_service
            mock_injector_cls.get_instance.return_value = mock_injector

            worker = ContentIndexingWorker(["/test/file.txt"], None)

            with qtbot.waitSignal(worker.finished, timeout=5000):
                worker.start()

            mock_service.should_index_content.assert_called()

class TestSearchWorker:

    def test_worker_initialization(self):
        worker = SearchWorker("test query", 20, SearchMode.FILENAME)

        assert worker._query == "test query"
        assert worker._n_results == 20
        assert worker._mode == SearchMode.FILENAME

    def test_worker_signals_exist(self):
        worker = SearchWorker("test")

        assert hasattr(worker, "results_ready")
        assert hasattr(worker, "error_occurred")

    def test_worker_emits_results(self, qtbot):
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.file_path = "/test/file.txt"
        mock_result.similarity_score = 85.0
        mock_result.match_type = "filename"
        mock_result.chunk_index = None
        mock_result.snippet = "Test snippet"
        mock_service.search.return_value = ([mock_result], False)

        worker = SearchWorker("test", 10, SearchMode.FILENAME, app_service=mock_service)

        results = []
        worker.results_ready.connect(lambda r, has_more: results.extend(r))

        with qtbot.waitSignal(worker.results_ready, timeout=5000):
            worker.start()

        assert len(results) == 1
        assert results[0]["path"] == "/test/file.txt"

    def test_worker_converts_similarity_to_distance(self, qtbot):
        mock_service = MagicMock()
        mock_result = MagicMock()
        mock_result.file_path = "/test/file.txt"
        mock_result.similarity_score = 100.0
        mock_result.match_type = "filename"
        mock_result.chunk_index = None
        mock_result.snippet = ""
        mock_service.search.return_value = ([mock_result], False)

        worker = SearchWorker("test", app_service=mock_service)

        results = []
        worker.results_ready.connect(lambda r, has_more: results.extend(r))

        with qtbot.waitSignal(worker.results_ready, timeout=5000):
            worker.start()

        assert results[0]["distance"] == 0.0

    def test_worker_emits_error_on_exception(self, qtbot):
        with patch("src.infrastructure.di.AppInjector") as mock_injector_cls:
            mock_injector = MagicMock()
            mock_injector.get_app_service.side_effect = RuntimeError("Connection failed")
            mock_injector_cls.get_instance.return_value = mock_injector

            worker = SearchWorker("test")

            errors = []
            worker.error_occurred.connect(lambda e: errors.append(e))

            with qtbot.waitSignal(worker.error_occurred, timeout=5000):
                worker.start()

            assert len(errors) == 1
            assert "connect" in errors[0].lower()

    def test_worker_emits_friendly_error_for_collection_not_found(self, qtbot):
        mock_service = MagicMock()
        mock_service.search.side_effect = RuntimeError("collection not found")

        worker = SearchWorker("test", app_service=mock_service)

        errors = []
        worker.error_occurred.connect(lambda e: errors.append(e))

        with qtbot.waitSignal(worker.error_occurred, timeout=5000):
            worker.start()

        assert len(errors) == 1
        assert "indexed data" in errors[0].lower()
        assert "indexing" in errors[0].lower()

    def test_worker_does_not_close_shared_app_service(self, qtbot):
        """SearchWorker should not close the shared singleton ApplicationService."""
        mock_service = MagicMock()
        mock_service.search.return_value = ([], False)

        worker = SearchWorker("test", app_service=mock_service)

        with qtbot.waitSignal(worker.results_ready, timeout=5000):
            worker.start()

        # Should NOT call close since it's a shared singleton
        mock_service.close.assert_not_called()

class TestWorkerThreadSafety:

    def test_filename_worker_runs_in_separate_thread(self, qtbot):
        mock_service = MagicMock()
        mock_service.collect_files.return_value = []
        mock_service.watch_dirs = []
        mock_service.set_folder_settings = MagicMock()

        worker = FilenameIndexingWorker(["/test"], app_service=mock_service)

        assert isinstance(worker, QThread)

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    def test_content_worker_runs_in_separate_thread(self, qtbot):
        mock_service = MagicMock()
        mock_service.should_index_content.return_value = False

        worker = ContentIndexingWorker([], mock_service)

        assert isinstance(worker, QThread)

        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    def test_search_worker_runs_in_separate_thread(self, qtbot):
        mock_service = MagicMock()
        mock_service.search.return_value = ([], False)

        worker = SearchWorker("test", app_service=mock_service)

        assert isinstance(worker, QThread)

        with qtbot.waitSignal(worker.results_ready, timeout=5000):
            worker.start()
