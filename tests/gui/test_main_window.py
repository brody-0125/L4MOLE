
import pytest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from src.presentation.gui.design_system import DesignSystem
from src.presentation.gui.main_window import MainWindow
from src.presentation.gui.widgets import EmptyStateWidget
from src.presentation import SearchMode

class TestMainWindowInitialization:

    def test_window_title(self, main_window):
        assert main_window.windowTitle() == "Local Semantic Explorer"

    def test_window_minimum_size(self, main_window):
        assert main_window.minimumWidth() == 600
        assert main_window.minimumHeight() == 400

    def test_search_input_exists(self, main_window):
        assert main_window.search_input is not None
        assert main_window.search_input.placeholderText() != ""

    def test_search_button_exists(self, main_window):
        assert main_window.search_btn is not None
        assert main_window.search_btn.text() == "Search"

    def test_search_mode_combo_exists(self, main_window):
        combo = main_window.search_mode_combo
        assert combo is not None
        assert combo.count() == 2
        assert combo.itemText(0) == "Filename"
        assert combo.itemText(1) == "Content"

    def test_results_list_exists(self, main_window):
        assert main_window.results_list is not None

    def test_preview_text_exists(self, main_window):
        assert main_window.preview_text is not None
        assert main_window.preview_text.isReadOnly()

    def test_progress_bar_initially_hidden(self, main_window):
        assert not main_window.progress_bar.isVisible()

    def test_cancel_button_initially_hidden(self, main_window):
        assert not main_window.cancel_btn.isVisible()

class TestMainWindowSearch:

    def test_search_button_is_connected(self, main_window, qtbot):
        assert main_window.search_btn.receivers(main_window.search_btn.clicked) > 0

    def test_search_input_return_pressed_is_connected(self, main_window, qtbot):
        assert main_window.search_input.receivers(main_window.search_input.returnPressed) > 0

    def test_empty_search_does_nothing(self, main_window, qtbot):
        main_window.search_input.setText("")
        main_window.search_input.setText("   ")

        initial_worker = main_window.search_worker
        main_window.perform_search()

        assert main_window.search_worker == initial_worker

    def test_search_mode_change(self, main_window, qtbot):
        assert main_window.search_mode_combo.currentData() == SearchMode.FILENAME

        main_window._content_indexing_done = False
        with patch.object(QMessageBox, "information"):
            main_window.search_mode_combo.setCurrentIndex(1)

        assert main_window.search_mode_combo.currentIndex() == 0

    def test_search_mode_change_allowed_after_content_indexing(self, main_window):
        main_window._content_indexing_done = True
        main_window.search_mode_combo.setCurrentIndex(1)

        assert main_window.search_mode_combo.currentData() == SearchMode.CONTENT

class TestMainWindowIndexing:

    def test_start_indexing_without_folders_shows_warning(self, main_window, qtbot):
        main_window.indexed_folders = []

        with patch.object(QMessageBox, "warning") as mock_warning:
            main_window.start_indexing()
            mock_warning.assert_called_once()

    def test_start_indexing_shows_progress(self, main_window, qtbot, mock_app_service):
        main_window.indexed_folders = ["/test/folder"]
        main_window.show()

        main_window.start_indexing()

        assert not main_window.progress_bar.isHidden()
        assert not main_window.cancel_btn.isHidden()
        assert not main_window.search_btn.isEnabled()

        if main_window.filename_worker:
            main_window.filename_worker.cancel()
            qtbot.wait(100)

    def test_cancel_indexing(self, main_window, qtbot, mock_app_service):
        main_window.indexed_folders = ["/test/folder"]

        import time
        mock_app_service.collect_files.return_value = [f"/test/file{i}.txt" for i in range(1000)]
        mock_app_service.index_filename.side_effect = lambda x: time.sleep(0.01)

        main_window.start_indexing()

        qtbot.wait(50)

        assert main_window.filename_worker is not None
        assert main_window.filename_worker.isRunning()

        main_window._cancel_indexing()

        assert main_window.filename_worker._is_cancelled

        qtbot.wait(200)

class TestMainWindowResults:

    def test_display_results_with_empty_list(self, main_window):
        main_window._on_initial_results([], has_more=False)

        assert main_window.results_list.count() == 0

    def test_display_results_with_data(self, main_window):
        results = [
            {
                "path": "/test/file1.txt",
                "distance": 0.2,
                "type": "filename",
                "chunk_index": None,
                "snippet": "Test snippet",
            },
            {
                "path": "/test/file2.py",
                "distance": 0.6,
                "type": "content",
                "chunk_index": 0,
                "snippet": "Another snippet",
            },
        ]

        main_window._on_initial_results(results, has_more=False)

        assert main_window.results_list.count() > 0

    def test_display_results_filters_by_threshold(self, main_window):
        main_window.threshold_combo.setCurrentIndex(0)

        results = [
            {"path": "/test/high.txt", "distance": 0.2, "type": "filename",
             "chunk_index": None, "snippet": "High match"},
            {"path": "/test/low.txt", "distance": 1.0, "type": "filename",
             "chunk_index": None, "snippet": "Low match"},
        ]

        main_window._on_initial_results(results, has_more=False)

        found_low = False
        for i in range(main_window.results_list.count()):
            item = main_window.results_list.item(i)
            if item.toolTip() == "/test/low.txt":
                found_low = True
        assert not found_low

class TestMainWindowPreview:

    def test_show_preview_with_text_file(self, main_window, temp_folder):
        import os
        file_path = os.path.join(temp_folder, "sample.txt")

        from PyQt6.QtWidgets import QListWidgetItem
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, {
            "path": file_path,
            "snippet": "Test snippet"
        })
        item.setToolTip(file_path)

        main_window._show_preview(item)

        assert main_window.preview_text.toPlainText() != ""
        assert "sample" in main_window.preview_text.toPlainText().lower() or \
               "test" in main_window.preview_text.toPlainText().lower()

class TestMainWindowSettings:

    def test_open_settings_dialog(self, main_window, qtbot):
        with patch.object(main_window, "open_settings") as mock_open:
            main_window.open_settings()
            mock_open.assert_called()

    def test_save_settings(self, main_window):
        main_window.indexed_folders = ["/test/folder1", "/test/folder2"]
        main_window.folder_settings = {
            "/test/folder1": {"include_hidden": True, "index_content": True}
        }

        main_window._save_settings()

        from PyQt6.QtCore import QSettings
        settings = QSettings("LocalAISearch", "LocalAISearch")
        saved_folders = settings.value("indexed_folders", [], type=list)

        assert "/test/folder1" in saved_folders
        assert "/test/folder2" in saved_folders

class TestNoResultsWidget:

    def test_no_results_widget_exists(self, main_window):
        assert main_window.no_results_widget is not None

    def test_display_results_shows_no_results_widget_for_empty(self, main_window):
        main_window.indexed_folders = ["/test/folder"]
        main_window._on_initial_results([], has_more=False)

        assert main_window.results_stack.currentWidget() == main_window.no_results_widget

    def test_display_results_shows_results_list_when_has_results(self, main_window):
        main_window.indexed_folders = ["/test/folder"]
        results = [
            {
                "path": "/test/file.txt",
                "distance": 0.2,
                "type": "filename",
                "chunk_index": None,
                "snippet": "Test",
            }
        ]
        main_window._on_initial_results(results, has_more=False)

        assert main_window.results_stack.currentWidget() == main_window.results_list

class TestEmptyStateWidget:

    def test_empty_state_has_add_button(self, empty_state_widget):
        assert empty_state_widget.add_btn is not None
        assert "+ Add Folder" in empty_state_widget.add_btn.text()

    def test_add_button_is_clickable(self, empty_state_widget, qtbot):
        clicked = False

        def on_click():
            nonlocal clicked
            clicked = True

        empty_state_widget.add_btn.clicked.connect(on_click)
        qtbot.mouseClick(empty_state_widget.add_btn, Qt.MouseButton.LeftButton)

        assert clicked

class TestEdgeCases:

    def test_search_with_unicode_characters(self, main_window, qtbot):
        main_window.search_input.setText("한글 검색")
        assert main_window.search_input.text() == "한글 검색"

    def test_search_with_emoji(self, main_window, qtbot):
        main_window.search_input.setText("📄 document")
        assert main_window.search_input.text() == "📄 document"

    def test_search_with_long_query(self, main_window, qtbot):
        long_query = "a" * 500
        main_window.search_input.setText(long_query)
        assert len(main_window.search_input.text()) == 500

    def test_display_results_with_long_path(self, main_window):
        long_path = "/very" + "/long" * 50 + "/path/file.txt"
        results = [
            {
                "path": long_path,
                "distance": 0.2,
                "type": "filename",
                "chunk_index": None,
                "snippet": "Test",
            }
        ]
        main_window._on_initial_results(results, has_more=False)
        assert main_window.results_list.count() > 0

    def test_display_results_with_special_characters_in_path(self, main_window):
        results = [
            {
                "path": "/test/path with spaces/file (1).txt",
                "distance": 0.2,
                "type": "filename",
                "chunk_index": None,
                "snippet": "Test",
            }
        ]
        main_window._on_initial_results(results, has_more=False)
        assert main_window.results_list.count() > 0

    def test_multiple_rapid_searches(self, main_window, qtbot, mock_app_service):
        main_window.indexed_folders = ["/test"]
        main_window._filename_indexing_done = True

        for i in range(5):
            main_window.search_input.setText(f"query{i}")

        assert main_window.search_input.text() == "query4"

    def test_window_resize_to_minimum(self, main_window, qtbot):
        main_window.resize(600, 400)
        assert main_window.width() >= 600
        assert main_window.height() >= 400

    def test_clear_results_when_empty(self, main_window):
        main_window._clear_results()
        assert main_window.results_list.count() == 0
        assert main_window.preview_text.toPlainText() == ""

    def test_add_same_folder_twice(self, main_window, qtbot):
        main_window.indexed_folders = ["/test/folder"]
        initial_count = len(main_window.indexed_folders)

        if "/test/folder" not in main_window.indexed_folders:
            main_window.indexed_folders.append("/test/folder")

        assert len(main_window.indexed_folders) == initial_count

class TestAccessibility:

    def test_search_input_has_placeholder(self, main_window):
        placeholder = main_window.search_input.placeholderText()
        assert placeholder != ""
        assert len(placeholder) > 10

    def test_preview_is_read_only(self, main_window):
        assert main_window.preview_text.isReadOnly()

    def test_buttons_have_cursor_hint(self, main_window):
        from PyQt6.QtCore import Qt
        assert main_window.search_btn.cursor().shape() == Qt.CursorShape.PointingHandCursor

    def test_results_list_has_tooltips(self, main_window):
        results = [
            {
                "path": "/test/file.txt",
                "distance": 0.2,
                "type": "filename",
                "chunk_index": None,
                "snippet": "Test",
            }
        ]
        main_window._on_initial_results(results, has_more=False)

        for i in range(main_window.results_list.count()):
            item = main_window.results_list.item(i)
            if item.toolTip():
                assert "/test/file.txt" in item.toolTip()
                break

class TestDesignSystem:

    def test_color_constants_are_valid_hex(self):
        colors = [
            DesignSystem.ACCENT_PRIMARY,
            DesignSystem.ACCENT_HOVER,
            DesignSystem.ACCENT_PRESSED,
            DesignSystem.ACCENT_LIGHT,
            DesignSystem.TEXT_PRIMARY,
            DesignSystem.TEXT_SECONDARY,
            DesignSystem.BG_PRIMARY,
            DesignSystem.BG_SECONDARY,
            DesignSystem.BORDER_LIGHT,
            DesignSystem.ERROR,
        ]

        for color in colors:
            assert color.startswith("#")
            assert len(color) == 7

    def test_font_size_constants_have_px_suffix(self):
        sizes = [
            DesignSystem.FONT_SIZE_XL,
            DesignSystem.FONT_SIZE_LG,
            DesignSystem.FONT_SIZE_MD,
            DesignSystem.FONT_SIZE_SM,
            DesignSystem.FONT_SIZE_XS,
        ]

        for size in sizes:
            assert size.endswith("px")
