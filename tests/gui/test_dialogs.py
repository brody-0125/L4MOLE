
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from src.presentation.gui.dialogs import FolderSettingsDialog, SettingsDialog

class TestFolderSettingsDialog:

    def test_dialog_initialization(self, folder_settings_dialog):
        assert folder_settings_dialog.windowTitle() == "Folder Settings"
        assert folder_settings_dialog.width() >= 450
        assert folder_settings_dialog.height() >= 220

    def test_dialog_has_content_checkbox(self, folder_settings_dialog):
        assert folder_settings_dialog.content_checkbox is not None
        assert "Content indexing" in folder_settings_dialog.content_checkbox.text()

    def test_dialog_has_hidden_checkbox(self, folder_settings_dialog):
        assert folder_settings_dialog.hidden_checkbox is not None
        assert "hidden files" in folder_settings_dialog.hidden_checkbox.text().lower()

    def test_initial_values_from_constructor(self, qtbot):
        dialog = FolderSettingsDialog(
            parent=None,
            folder_path="/test/folder",
            include_hidden=True,
            index_content=False
        )
        qtbot.addWidget(dialog)

        assert dialog.hidden_checkbox.isChecked() is True
        assert dialog.content_checkbox.isChecked() is False

    def test_get_include_hidden(self, folder_settings_dialog, qtbot):
        assert folder_settings_dialog.get_include_hidden() is False

        folder_settings_dialog.hidden_checkbox.setChecked(True)
        assert folder_settings_dialog.get_include_hidden() is True

    def test_get_index_content(self, folder_settings_dialog, qtbot):
        assert folder_settings_dialog.get_index_content() is True

        folder_settings_dialog.content_checkbox.setChecked(False)
        assert folder_settings_dialog.get_index_content() is False

    def test_checkbox_toggle(self, folder_settings_dialog, qtbot):
        initial_hidden = folder_settings_dialog.hidden_checkbox.isChecked()
        folder_settings_dialog.hidden_checkbox.click()
        assert folder_settings_dialog.hidden_checkbox.isChecked() != initial_hidden

        initial_content = folder_settings_dialog.content_checkbox.isChecked()
        folder_settings_dialog.content_checkbox.click()
        assert folder_settings_dialog.content_checkbox.isChecked() != initial_content

class TestSettingsDialog:

    def test_dialog_initialization(self, settings_dialog):
        assert settings_dialog.windowTitle() == "Settings - Folder Management"
        assert settings_dialog.width() >= 600
        assert settings_dialog.height() >= 450

    def test_dialog_shows_initial_folders(self, settings_dialog):
        assert settings_dialog.list_widget.count() == 2

    def test_dialog_has_list_widget(self, settings_dialog):
        assert settings_dialog.list_widget is not None

    def test_dialog_has_add_remove_methods(self, settings_dialog):
        assert hasattr(settings_dialog, "add_folder")
        assert hasattr(settings_dialog, "remove_folder")
        assert callable(settings_dialog.add_folder)
        assert callable(settings_dialog.remove_folder)

    def test_get_folders_returns_list(self, settings_dialog):
        folders = settings_dialog.get_folders()
        assert isinstance(folders, list)
        assert len(folders) == 2
        assert "/folder1" in folders
        assert "/folder2" in folders

    def test_get_folder_settings_returns_dict(self, settings_dialog):
        settings = settings_dialog.get_folder_settings()
        assert isinstance(settings, dict)
        assert "/folder1" in settings
        assert settings["/folder1"]["include_hidden"] is False
        assert settings["/folder1"]["index_content"] is True

    def test_remove_folder_without_selection(self, settings_dialog, qtbot):
        settings_dialog.list_widget.clearSelection()
        initial_count = settings_dialog.list_widget.count()

        settings_dialog.remove_folder()

        assert settings_dialog.list_widget.count() == initial_count

    def test_remove_folder_with_selection(self, settings_dialog, qtbot):
        settings_dialog.list_widget.setCurrentRow(0)
        initial_count = settings_dialog.list_widget.count()

        settings_dialog.remove_folder()

        assert settings_dialog.list_widget.count() == initial_count - 1
        assert len(settings_dialog.get_folders()) == initial_count - 1

    def test_add_folder_with_file_dialog(self, settings_dialog, qtbot):
        with patch.object(QFileDialog, "getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = "/new/folder"

            with patch.object(FolderSettingsDialog, "exec") as mock_exec:
                mock_exec.return_value = True

                with patch.object(
                    FolderSettingsDialog, "get_include_hidden", return_value=False
                ):
                    with patch.object(
                        FolderSettingsDialog, "get_index_content", return_value=True
                    ):
                        settings_dialog.add_folder()

                        assert "/new/folder" in settings_dialog.get_folders()

    def test_add_folder_cancelled(self, settings_dialog, qtbot):
        initial_count = len(settings_dialog.get_folders())

        with patch.object(QFileDialog, "getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = ""

            settings_dialog.add_folder()

            assert len(settings_dialog.get_folders()) == initial_count

    def test_add_duplicate_folder_prevented(self, settings_dialog, qtbot):
        initial_count = len(settings_dialog.get_folders())

        with patch.object(QFileDialog, "getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = "/folder1"

            settings_dialog.add_folder()

            assert len(settings_dialog.get_folders()) == initial_count

    def test_folder_list_refresh(self, settings_dialog):
        settings_dialog.folders.append("/new/folder")
        settings_dialog.folder_settings["/new/folder"] = {
            "include_hidden": True,
            "index_content": False
        }

        settings_dialog._refresh_folder_list()

        assert settings_dialog.list_widget.count() == 3

    def test_edit_folder_settings_shows_dialog(self, settings_dialog, qtbot):
        settings_dialog.list_widget.setCurrentRow(0)
        item = settings_dialog.list_widget.item(0)

        with patch.object(FolderSettingsDialog, "exec") as mock_exec:
            mock_exec.return_value = False

            settings_dialog._edit_folder_settings(item)

            mock_exec.assert_called_once()

    def test_edit_folder_settings_updates_settings(self, settings_dialog, qtbot):
        settings_dialog.list_widget.setCurrentRow(0)
        item = settings_dialog.list_widget.item(0)
        folder = item.data(Qt.ItemDataRole.UserRole)

        with patch("src.presentation.gui.dialogs.FolderSettingsDialog") as MockDialog:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = True
            mock_instance.get_include_hidden.return_value = True
            mock_instance.get_index_content.return_value = False
            MockDialog.return_value = mock_instance

            settings_dialog._edit_folder_settings(item)

            settings = settings_dialog.folder_settings[folder]
            assert settings["include_hidden"] is True
            assert settings["index_content"] is False

class TestSettingsDialogEmpty:

    def test_empty_dialog_initialization(self, qtbot):
        dialog = SettingsDialog(parent=None, current_folders=[], folder_settings={})
        qtbot.addWidget(dialog)

        assert dialog.list_widget.count() == 0
        assert len(dialog.get_folders()) == 0

    def test_empty_dialog_add_first_folder(self, qtbot):
        dialog = SettingsDialog(parent=None, current_folders=[], folder_settings={})
        qtbot.addWidget(dialog)

        with patch.object(QFileDialog, "getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = "/first/folder"

            with patch.object(FolderSettingsDialog, "exec") as mock_exec:
                mock_exec.return_value = True

                with patch.object(
                    FolderSettingsDialog, "get_include_hidden", return_value=False
                ):
                    with patch.object(
                        FolderSettingsDialog, "get_index_content", return_value=True
                    ):
                        dialog.add_folder()

                        assert len(dialog.get_folders()) == 1
                        assert "/first/folder" in dialog.get_folders()

class TestDialogInteraction:

    def test_folder_settings_dialog_accept(self, qtbot):
        dialog = FolderSettingsDialog(
            parent=None,
            folder_path="/test",
            include_hidden=False,
            index_content=True
        )
        qtbot.addWidget(dialog)

        dialog.hidden_checkbox.setChecked(True)
        dialog.content_checkbox.setChecked(False)

        dialog.accept()

        assert dialog.get_include_hidden() is True
        assert dialog.get_index_content() is False

    def test_settings_dialog_preserves_settings_on_refresh(self, settings_dialog):
        original_settings = settings_dialog.folder_settings.copy()

        settings_dialog._refresh_folder_list()

        assert settings_dialog.folder_settings == original_settings

    def test_settings_dialog_removes_settings_with_folder(self, settings_dialog):
        settings_dialog.list_widget.setCurrentRow(0)
        item = settings_dialog.list_widget.item(0)
        folder = item.data(Qt.ItemDataRole.UserRole)

        assert folder in settings_dialog.folder_settings

        settings_dialog.remove_folder()

        assert folder not in settings_dialog.folder_settings
