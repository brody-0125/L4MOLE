
import os
import platform
import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from src.infrastructure.process_manager import (
    _managed_processes,
    _signal_handler,
    cleanup_all,
    cleanup_managed_processes,
    get_app_data_dir,
    get_ollama_processes,
    register_cleanup,
    set_started_ollama,
    stop_ollama,
)


class TestRegisterCleanup:

    def test_register_cleanup_sets_atexit_handler(self):
        import src.infrastructure.process_manager as pm

        pm._cleanup_registered = False

        with patch("atexit.register") as mock_atexit:
            with patch("signal.signal") as mock_signal:
                register_cleanup()

                mock_atexit.assert_called_once_with(cleanup_all)

    def test_register_cleanup_sets_signal_handlers_on_unix(self):
        import src.infrastructure.process_manager as pm

        pm._cleanup_registered = False

        with patch("platform.system", return_value="Darwin"):
            with patch("atexit.register"):
                with patch("signal.signal") as mock_signal:
                    register_cleanup()

                    mock_signal.assert_any_call(signal.SIGTERM, _signal_handler)
                    mock_signal.assert_any_call(signal.SIGINT, _signal_handler)

    def test_register_cleanup_skips_signal_on_windows(self):
        import src.infrastructure.process_manager as pm

        pm._cleanup_registered = False

        with patch("platform.system", return_value="Windows"):
            with patch("atexit.register"):
                with patch("signal.signal") as mock_signal:
                    register_cleanup()

                    mock_signal.assert_not_called()

    def test_register_cleanup_idempotent(self):
        import src.infrastructure.process_manager as pm

        pm._cleanup_registered = True

        with patch("atexit.register") as mock_atexit:
            register_cleanup()

            mock_atexit.assert_not_called()


class TestSignalHandler:

    def test_signal_handler_calls_cleanup_and_exits(self):
        with patch("src.infrastructure.process_manager.cleanup_all") as mock_cleanup:
            with patch("sys.exit") as mock_exit:
                _signal_handler(signal.SIGTERM, None)

                mock_cleanup.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestSetStartedOllama:

    def test_set_started_ollama_true(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = False
        set_started_ollama(True)

        assert pm._started_ollama is True

    def test_set_started_ollama_false(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = True
        set_started_ollama(False)

        assert pm._started_ollama is False


class TestGetOllamaProcesses:

    def test_get_ollama_processes_darwin(self):
        with patch("platform.system", return_value="Darwin"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "12345\n67890\n"

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                pids = get_ollama_processes()

                mock_run.assert_called_once()
                assert pids == [12345, 67890]

    def test_get_ollama_processes_darwin_no_processes(self):
        with patch("platform.system", return_value="Darwin"):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""

            with patch("subprocess.run", return_value=mock_result):
                pids = get_ollama_processes()

                assert pids == []

    def test_get_ollama_processes_windows(self):
        with patch("platform.system", return_value="Windows"):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '"ollama.exe","1234","Console","1","50,000 K"\n'

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                pids = get_ollama_processes()

                mock_run.assert_called_once()
                assert 1234 in pids

    def test_get_ollama_processes_handles_exception(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run", side_effect=Exception("Test error")):
                pids = get_ollama_processes()

                assert pids == []

    def test_get_ollama_processes_handles_timeout(self):
        with patch("platform.system", return_value="Darwin"):
            with patch(
                "subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)
            ):
                pids = get_ollama_processes()

                assert pids == []


class TestStopOllama:

    def test_stop_ollama_not_started_by_us(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = False

        result = stop_ollama()

        assert result is False

    def test_stop_ollama_darwin_quit_app(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = True

        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as mock_run:
                with patch(
                    "src.infrastructure.process_manager.get_ollama_processes",
                    return_value=[],
                ):
                    with patch("time.sleep"):
                        result = stop_ollama()

                        mock_run.assert_called()
                        assert result is True

    def test_stop_ollama_kills_processes(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = True

        with patch("platform.system", return_value="Linux"):
            with patch(
                "src.infrastructure.process_manager.get_ollama_processes",
                return_value=[12345],
            ):
                with patch("os.kill") as mock_kill:
                    result = stop_ollama()

                    mock_kill.assert_called_once_with(12345, signal.SIGTERM)
                    assert result is True

    def test_stop_ollama_windows_taskkill(self):
        import src.infrastructure.process_manager as pm

        pm._started_ollama = True

        with patch("platform.system", return_value="Windows"):
            with patch(
                "src.infrastructure.process_manager.get_ollama_processes",
                return_value=[12345],
            ):
                with patch("subprocess.run") as mock_run:
                    result = stop_ollama()

                    mock_run.assert_called()
                    assert result is True


class TestCleanupManagedProcesses:

    def test_cleanup_managed_processes_terminates_running(self):
        import src.infrastructure.process_manager as pm

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345

        pm._managed_processes = [mock_process]

        cleanup_managed_processes()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        assert pm._managed_processes == []

    def test_cleanup_managed_processes_force_kills_on_timeout(self):
        import src.infrastructure.process_manager as pm

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

        pm._managed_processes = [mock_process]

        cleanup_managed_processes()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_cleanup_managed_processes_skips_already_terminated(self):
        import src.infrastructure.process_manager as pm

        mock_process = MagicMock()
        mock_process.poll.return_value = 0

        pm._managed_processes = [mock_process]

        cleanup_managed_processes()

        mock_process.terminate.assert_not_called()


class TestCleanupAll:

    def test_cleanup_all_calls_both_cleanups(self):
        with patch(
            "src.infrastructure.process_manager.cleanup_managed_processes"
        ) as mock_managed:
            with patch("src.infrastructure.process_manager.stop_ollama") as mock_ollama:
                cleanup_all()

                mock_managed.assert_called_once()
                mock_ollama.assert_called_once()


class TestGetAppDataDir:

    def test_get_app_data_dir_darwin(self):
        with patch("platform.system", return_value="Darwin"):
            with patch("os.path.expanduser") as mock_expand:
                mock_expand.return_value = "/Users/test"
                with patch("os.makedirs") as mock_makedirs:
                    result = get_app_data_dir()

                    assert "Library/Application Support" in result or "L4MOLE" in result
                    mock_makedirs.assert_called_once()

    def test_get_app_data_dir_windows(self):
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local"}):
                with patch("os.makedirs") as mock_makedirs:
                    result = get_app_data_dir()

                    assert "L4MOLE" in result
                    mock_makedirs.assert_called_once()

    def test_get_app_data_dir_linux(self):
        with patch("platform.system", return_value="Linux"):
            with patch.dict(os.environ, {"XDG_DATA_HOME": "/home/test/.local/share"}):
                with patch("os.makedirs") as mock_makedirs:
                    result = get_app_data_dir()

                    assert "L4MOLE" in result
                    mock_makedirs.assert_called_once()

    def test_get_app_data_dir_linux_fallback(self):
        with patch("platform.system", return_value="Linux"):
            with patch.dict(os.environ, {}, clear=True):
                with patch("os.path.expanduser", return_value="/home/test"):
                    with patch("os.makedirs") as mock_makedirs:
                        result = get_app_data_dir()

                        assert "L4MOLE" in result
