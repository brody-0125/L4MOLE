
import os
import platform
import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

from src.infrastructure.ollama_utils import (
    OLLAMA_LIST_TIMEOUT,
    OLLAMA_STARTUP_TIMEOUT,
    _start_ollama_linux,
    _start_ollama_macos,
    _start_ollama_windows,
    _wait_for_ollama,
    ensure_ollama_running,
    get_ollama_cmd,
    is_ollama_running,
    start_ollama,
)


class TestGetOllamaCmd:

    def test_returns_path_from_which(self):
        with patch("shutil.which", return_value="/usr/bin/ollama"):
            result = get_ollama_cmd()

            assert result == "/usr/bin/ollama"

    def test_darwin_fallback_homebrew(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Darwin"):
                with patch("os.path.exists") as mock_exists:
                    mock_exists.side_effect = lambda p: p == "/opt/homebrew/bin/ollama"

                    result = get_ollama_cmd()

                    assert result == "/opt/homebrew/bin/ollama"

    def test_darwin_fallback_usrlocal(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Darwin"):
                with patch("os.path.exists") as mock_exists:
                    mock_exists.side_effect = lambda p: p == "/usr/local/bin/ollama"

                    result = get_ollama_cmd()

                    assert result == "/usr/local/bin/ollama"

    def test_darwin_default_fallback(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Darwin"):
                with patch("os.path.exists", return_value=False):
                    result = get_ollama_cmd()

                    assert result == "ollama"

    def test_windows_localappdata(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Windows"):
                with patch.dict(
                    os.environ,
                    {
                        "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                        "PROGRAMFILES": "C:\\Program Files",
                        "USERPROFILE": "C:\\Users\\Test",
                    },
                ):
                    expected = os.path.join(
                        "C:\\Users\\Test\\AppData\\Local",
                        "Programs",
                        "Ollama",
                        "ollama.exe",
                    )
                    with patch(
                        "src.infrastructure.ollama_utils.os.path.exists"
                    ) as mock_exists:
                        mock_exists.side_effect = lambda p: p == expected

                        result = get_ollama_cmd()

                        assert result == expected

    def test_windows_default_fallback(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Windows"):
                with patch.dict(
                    os.environ,
                    {
                        "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                        "PROGRAMFILES": "C:\\Program Files",
                        "USERPROFILE": "C:\\Users\\Test",
                    },
                ):
                    with patch("os.path.exists", return_value=False):
                        result = get_ollama_cmd()

                        assert result == "ollama"

    def test_linux_default(self):
        with patch("shutil.which", return_value=None):
            with patch("platform.system", return_value="Linux"):
                result = get_ollama_cmd()

                assert result == "ollama"


class TestIsOllamaRunning:

    def test_returns_true_when_list_succeeds(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = is_ollama_running()

                assert result is True
                mock_run.assert_called_once()

    def test_returns_false_on_called_process_error(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "ollama"),
            ):
                result = is_ollama_running()

                assert result is False

    def test_returns_false_on_file_not_found(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = is_ollama_running()

                assert result is False

    def test_returns_false_on_timeout(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired("cmd", OLLAMA_LIST_TIMEOUT),
            ):
                result = is_ollama_running()

                assert result is False


class TestWaitForOllama:

    def test_returns_true_immediately_if_running(self):
        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running", return_value=True
        ):
            result = _wait_for_ollama(timeout=5)

            assert result is True

    def test_returns_true_after_waiting(self):
        call_count = [0]

        def mock_is_running():
            call_count[0] += 1
            return call_count[0] >= 3

        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running",
            side_effect=mock_is_running,
        ):
            with patch("time.sleep"):
                result = _wait_for_ollama(timeout=5)

                assert result is True
                assert call_count[0] == 3

    def test_returns_false_after_timeout(self):
        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running", return_value=False
        ):
            with patch("time.sleep"):
                result = _wait_for_ollama(timeout=3)

                assert result is False


class TestStartOllamaMacos:

    def test_starts_via_open_app(self):
        with patch("subprocess.run") as mock_run:
            with patch(
                "src.infrastructure.ollama_utils._wait_for_ollama", return_value=True
            ):
                result = _start_ollama_macos("/usr/bin/ollama")

                assert result is True
                mock_run.assert_called_once()

    def test_falls_back_to_serve_if_app_fails(self):
        with patch("subprocess.run", side_effect=Exception("App not found")):
            with patch("subprocess.Popen") as mock_popen:
                with patch(
                    "src.infrastructure.ollama_utils._wait_for_ollama", return_value=True
                ):
                    result = _start_ollama_macos("/usr/bin/ollama")

                    assert result is True
                    mock_popen.assert_called_once()

    def test_returns_false_if_both_fail(self):
        with patch("subprocess.run", side_effect=Exception("App not found")):
            with patch("subprocess.Popen", side_effect=Exception("Serve failed")):
                result = _start_ollama_macos("/usr/bin/ollama")

                assert result is False


class TestStartOllamaWindows:

    @pytest.fixture(autouse=True)
    def mock_windows_constants(self):
        if not hasattr(subprocess, "DETACHED_PROCESS"):
            subprocess.DETACHED_PROCESS = 0x00000008
        if not hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess.CREATE_NO_WINDOW = 0x08000000
        yield

    def test_starts_via_app_exe(self):
        with patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                "PROGRAMFILES": "C:\\Program Files",
            },
        ):
            with patch(
                "src.infrastructure.ollama_utils.os.path.exists"
            ) as mock_exists:
                mock_exists.side_effect = (
                    lambda p: "Programs" in p and "Ollama.exe" in p
                )
                with patch(
                    "src.infrastructure.ollama_utils.subprocess.Popen"
                ) as mock_popen:
                    with patch(
                        "src.infrastructure.ollama_utils._wait_for_ollama",
                        return_value=True,
                    ):
                        result = _start_ollama_windows("ollama.exe")

                        assert result is True
                        mock_popen.assert_called_once()

    def test_falls_back_to_serve(self):
        with patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                "PROGRAMFILES": "C:\\Program Files",
            },
        ):
            with patch(
                "src.infrastructure.ollama_utils.os.path.exists", return_value=False
            ):
                with patch(
                    "src.infrastructure.ollama_utils.subprocess.Popen"
                ) as mock_popen:
                    with patch(
                        "src.infrastructure.ollama_utils._wait_for_ollama",
                        return_value=True,
                    ):
                        result = _start_ollama_windows("ollama.exe")

                        assert result is True
                        mock_popen.assert_called_once()

    def test_returns_false_if_all_fail(self):
        with patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local",
                "PROGRAMFILES": "C:\\Program Files",
            },
        ):
            with patch(
                "src.infrastructure.ollama_utils.os.path.exists", return_value=False
            ):
                with patch(
                    "src.infrastructure.ollama_utils.subprocess.Popen",
                    side_effect=Exception("Failed"),
                ):
                    result = _start_ollama_windows("ollama.exe")

                    assert result is False


class TestStartOllamaLinux:

    def test_starts_serve(self):
        with patch("subprocess.Popen") as mock_popen:
            with patch(
                "src.infrastructure.ollama_utils._wait_for_ollama", return_value=True
            ):
                result = _start_ollama_linux("/usr/bin/ollama")

                assert result is True
                mock_popen.assert_called_once()

    def test_returns_false_on_failure(self):
        with patch("subprocess.Popen", side_effect=Exception("Failed")):
            result = _start_ollama_linux("/usr/bin/ollama")

            assert result is False


class TestStartOllama:

    def test_starts_on_darwin(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch("platform.system", return_value="Darwin"):
                with patch(
                    "src.infrastructure.ollama_utils._start_ollama_macos",
                    return_value=True,
                ) as mock_start:
                    result = start_ollama()

                    assert result is True
                    mock_start.assert_called_once_with("/usr/bin/ollama")

    def test_starts_on_windows(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="ollama.exe",
        ):
            with patch("platform.system", return_value="Windows"):
                with patch(
                    "src.infrastructure.ollama_utils._start_ollama_windows",
                    return_value=True,
                ) as mock_start:
                    result = start_ollama()

                    assert result is True
                    mock_start.assert_called_once_with("ollama.exe")

    def test_starts_on_linux(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="/usr/bin/ollama",
        ):
            with patch("platform.system", return_value="Linux"):
                with patch(
                    "src.infrastructure.ollama_utils._start_ollama_linux",
                    return_value=True,
                ) as mock_start:
                    result = start_ollama()

                    assert result is True
                    mock_start.assert_called_once_with("/usr/bin/ollama")

    def test_returns_false_for_unknown_os(self):
        with patch(
            "src.infrastructure.ollama_utils.get_ollama_cmd",
            return_value="ollama",
        ):
            with patch("platform.system", return_value="FreeBSD"):
                result = start_ollama()

                assert result is False


class TestEnsureOllamaRunning:

    def test_returns_true_if_already_running(self):
        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running", return_value=True
        ):
            result = ensure_ollama_running()

            assert result is True

    def test_starts_if_not_running(self):
        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running", return_value=False
        ):
            with patch(
                "src.infrastructure.ollama_utils.start_ollama", return_value=True
            ) as mock_start:
                result = ensure_ollama_running()

                assert result is True
                mock_start.assert_called_once()

    def test_returns_false_if_start_fails(self):
        with patch(
            "src.infrastructure.ollama_utils.is_ollama_running", return_value=False
        ):
            with patch(
                "src.infrastructure.ollama_utils.start_ollama", return_value=False
            ):
                result = ensure_ollama_running()

                assert result is False
