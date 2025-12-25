
import os
import tempfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from src.presentation.gui.design_system import DesignSystem
from src.presentation.gui.dialogs import FolderSettingsDialog, SettingsDialog
from src.presentation.gui.widgets import EmptyStateWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_folder() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        sample_txt = os.path.join(tmpdir, "sample.txt")
        with open(sample_txt, "w") as f:
            f.write("This is a sample text file for testing.")

        sample_py = os.path.join(tmpdir, "test_script.py")
        with open(sample_py, "w") as f:
            f.write("# Python test file\nprint('hello')")

        sample_md = os.path.join(tmpdir, "readme.md")
        with open(sample_md, "w") as f:
            f.write("# Readme\n\nTest markdown file.")

        yield tmpdir


@pytest.fixture
def mock_app_service():
    """Mock ApplicationService for testing workers and main window."""
    mock_service = MagicMock()
    mock_service.collect_files.return_value = ["/test/file1.txt", "/test/file2.py"]
    mock_service.index_filename.return_value = True
    mock_service.index_content.return_value = True
    mock_service.should_index_content.return_value = True
    mock_service.search.return_value = ([], False)
    mock_service.watch_dirs = []
    mock_service.set_folder_settings = MagicMock()
    mock_service.start_watching = MagicMock()
    mock_service.close = MagicMock()
    return mock_service


@pytest.fixture
def main_window(qtbot, mock_app_service):
    from PyQt6.QtCore import QSettings
    settings = QSettings("LocalAISearch", "LocalAISearch")
    settings.clear()
    settings.sync()

    # Mock the AppInjector at the infrastructure level before MainWindow init
    with patch("src.infrastructure.di.AppInjector") as mock_injector_cls:
        mock_injector = MagicMock()
        mock_injector.get_app_service.return_value = mock_app_service
        mock_injector_cls.get_instance.return_value = mock_injector
        mock_injector_cls.reset_instance = MagicMock()

        from src.presentation.gui.main_window import MainWindow
        window = MainWindow()
        qtbot.addWidget(window)
        yield window
        window.close()


@pytest.fixture
def empty_state_widget(qtbot):
    widget = EmptyStateWidget()
    qtbot.addWidget(widget)
    yield widget


@pytest.fixture
def folder_settings_dialog(qtbot):
    dialog = FolderSettingsDialog(
        parent=None,
        folder_path="/test/folder",
        include_hidden=False,
        index_content=True
    )
    qtbot.addWidget(dialog)
    yield dialog


@pytest.fixture
def settings_dialog(qtbot):
    dialog = SettingsDialog(
        parent=None,
        current_folders=["/folder1", "/folder2"],
        folder_settings={
            "/folder1": {"include_hidden": False, "index_content": True},
            "/folder2": {"include_hidden": True, "index_content": False},
        }
    )
    qtbot.addWidget(dialog)
    yield dialog
