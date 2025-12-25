
import os
import sys

from PyQt6.QtCore import QSettings, QSize, Qt, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ...domain.value_objects.search_query import SearchMode
from .design_system import DesignSystem
from .dialogs import FolderSettingsDialog, SettingsDialog
from .widgets import (
    EmptyStateWidget,
    InfiniteScrollListWidget,
    ResultItemWidget,
    SectionHeaderWidget,
)
from .workers import (
    ContentIndexingWorker,
    FilenameIndexingWorker,
    SearchWorker,
)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local Semantic Explorer")
        self.resize(900, 700)
        self.setMinimumSize(600, 400)

        self.settings = QSettings("LocalAISearch", "LocalAISearch")
        self.indexed_folders = self.settings.value("indexed_folders", [], type=list)
        self.search_history = self.settings.value("search_history", [], type=list)
        self.folder_settings = self._load_folder_settings()

        self.filename_worker = None
        self.content_worker = None
        self.search_worker = None
        self._worker_connections = []

        self._filename_indexing_done = False
        self._content_indexing_done = False
        self._collected_files = []

        from ...infrastructure.di import AppInjector
        self._app_injector = AppInjector.get_instance()
        self._app_service = None

        self._setup_ui()
        self._setup_shortcuts()
        self._apply_styles()

    @property
    def app_service(self):
        """Get the singleton ApplicationService instance (lazy initialization)."""
        if self._app_service is None:
            self._app_service = self._app_injector.get_app_service()
        return self._app_service

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 16, 20, 12)
        main_layout.setSpacing(16)

        search_group = self._create_search_area()
        main_layout.addWidget(search_group)

        splitter = self._create_results_area()
        main_layout.addWidget(splitter, 1)

        self._setup_status_bar()
        self._setup_menu_bar()
        self._setup_toolbar()

    def _create_search_area(self) -> QWidget:
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {DesignSystem.BG_SECONDARY};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(search_frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query (e.g., 'contract', 'report')")
        self.search_input.setMinimumHeight(44)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 22px;
                padding: 10px 18px;
                font-size: {DesignSystem.FONT_SIZE_LG};
                background-color: {DesignSystem.BG_PRIMARY};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {DesignSystem.ACCENT_PRIMARY};
                background-color: {DesignSystem.BG_PRIMARY};
            }}
            QLineEdit::placeholder {{
                color: {DesignSystem.TEXT_SECONDARY};
            }}
        """)
        self.search_input.returnPressed.connect(self.perform_search)

        self.search_btn = QPushButton("Search")
        self.search_btn.setMinimumSize(90, 44)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.ACCENT_PRIMARY};
                color: white;
                border: none;
                border-radius: 22px;
                font-size: {DesignSystem.FONT_SIZE_LG};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.ACCENT_PRESSED};
            }}
            QPushButton:disabled {{
                background-color: {DesignSystem.TEXT_DISABLED};
            }}
        """)
        self.search_btn.clicked.connect(self.perform_search)

        input_layout.addWidget(self.search_input, 1)
        input_layout.addWidget(self.search_btn)

        layout.addLayout(input_layout)

        options_layout = QHBoxLayout()
        options_layout.setSpacing(16)

        label_style = f"""
            color: {DesignSystem.TEXT_PRIMARY};
            font-size: {DesignSystem.FONT_SIZE_SM};
            font-weight: 500;
        """

        combo_style = f"""
            QComboBox {{
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 6px;
                padding: 6px 12px;
                padding-right: 24px;
                background-color: {DesignSystem.BG_PRIMARY};
                color: {DesignSystem.TEXT_PRIMARY};
                font-size: {DesignSystem.FONT_SIZE_SM};
                min-height: 28px;
            }}
            QComboBox:hover {{
                border-color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QComboBox:focus {{
                border-color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {DesignSystem.TEXT_SECONDARY};
                margin-right: 8px;
            }}
            QComboBox::down-arrow:hover {{
                border-top-color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background-color: {DesignSystem.BG_PRIMARY};
                selection-background-color: {DesignSystem.ACCENT_LIGHT};
                selection-color: {DesignSystem.ACCENT_PRIMARY};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 6px;
                padding: 4px;
            }}
        """

        filter_group_style = f"""
            QFrame {{
                background-color: {DesignSystem.BG_PRIMARY};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 8px;
                padding: 4px 8px;
            }}
        """

        mode_group = QFrame()
        mode_group.setStyleSheet(filter_group_style)
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(8, 6, 8, 6)
        mode_layout.setSpacing(4)

        mode_label = QLabel("Mode")
        mode_label.setStyleSheet(label_style)
        self.search_mode_combo = QComboBox()
        self.search_mode_combo.addItem("Filename", SearchMode.FILENAME)
        self.search_mode_combo.addItem("Content", SearchMode.CONTENT)
        self.search_mode_combo.setMinimumWidth(100)
        self.search_mode_combo.setStyleSheet(combo_style)
        self.search_mode_combo.currentIndexChanged.connect(self._on_search_mode_changed)

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.search_mode_combo)
        options_layout.addWidget(mode_group)

        result_group = QFrame()
        result_group.setStyleSheet(filter_group_style)
        result_layout = QHBoxLayout(result_group)
        result_layout.setContentsMargins(8, 6, 8, 6)
        result_layout.setSpacing(16)

        results_container = QVBoxLayout()
        results_container.setSpacing(4)
        results_label = QLabel("Results")
        results_label.setStyleSheet(label_style)
        self.results_count_combo = QComboBox()
        self.results_count_combo.addItems(["10", "20", "50", "100"])
        self.results_count_combo.setMinimumWidth(70)
        self.results_count_combo.setStyleSheet(combo_style)
        results_container.addWidget(results_label)
        results_container.addWidget(self.results_count_combo)
        result_layout.addLayout(results_container)

        threshold_container = QVBoxLayout()
        threshold_container.setSpacing(4)
        threshold_label = QLabel("Min Match")
        threshold_label.setStyleSheet(label_style)
        self.threshold_combo = QComboBox()
        self.threshold_combo.addItem("80%", 80)
        self.threshold_combo.addItem("70%", 70)
        self.threshold_combo.addItem("60%", 60)
        self.threshold_combo.addItem("50%", 50)
        self.threshold_combo.addItem("No limit", 0)
        self.threshold_combo.setMinimumWidth(100)
        self.threshold_combo.setStyleSheet(combo_style)
        self.threshold_combo.setToolTip("Only show results with match rate above this threshold")
        threshold_container.addWidget(threshold_label)
        threshold_container.addWidget(self.threshold_combo)
        result_layout.addLayout(threshold_container)

        options_layout.addWidget(result_group)
        options_layout.addStretch()

        self.indexing_status_label = QLabel("")
        self.indexing_status_label.setStyleSheet(f"""
            color: {DesignSystem.TEXT_SECONDARY};
            font-size: {DesignSystem.FONT_SIZE_SM};
            padding: 6px 12px;
        """)
        self.indexing_status_label.setVisible(False)
        options_layout.addWidget(self.indexing_status_label)

        layout.addLayout(options_layout)

        return search_frame

    def _create_results_area(self) -> QSplitter:
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        from PyQt6.QtGui import QColor

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)

        card_style = f"""
            QFrame {{
                background-color: {DesignSystem.BG_PRIMARY};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 12px;
            }}
        """

        left_panel = QFrame()
        left_panel.setObjectName("ResultsCard")
        left_panel.setStyleSheet(card_style)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_shadow = QGraphicsDropShadowEffect()
        left_shadow.setBlurRadius(20)
        left_shadow.setXOffset(0)
        left_shadow.setYOffset(2)
        left_shadow.setColor(QColor(0, 0, 0, 25))
        left_panel.setGraphicsEffect(left_shadow)

        results_header = QLabel("Search Results")
        results_header.setStyleSheet(f"""
            font-weight: 600;
            font-size: {DesignSystem.FONT_SIZE_LG};
            color: {DesignSystem.TEXT_PRIMARY};
            padding-bottom: 4px;
            border: none;
            background: transparent;
        """)
        left_layout.addWidget(results_header)

        self.results_stack = QStackedWidget()

        self.empty_state = EmptyStateWidget()
        self.empty_state.add_btn.clicked.connect(self._quick_add_folder)
        self.results_stack.addWidget(self.empty_state)

        self.results_list = InfiniteScrollListWidget()
        self.results_list.itemDoubleClicked.connect(self._open_file_from_result)
        self.results_list.itemClicked.connect(self._show_preview)
        self.results_list.load_more_requested.connect(self._load_more_results)
        self.results_stack.addWidget(self.results_list)

        self._current_query = ""
        self._current_mode = SearchMode.FILENAME
        self._current_offset = 0
        self._fetch_size = 20

        self.no_results_widget = QWidget()
        no_results_layout = QVBoxLayout(self.no_results_widget)
        no_results_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results_layout.setSpacing(12)

        no_results_icon = QFrame()
        no_results_icon.setFixedSize(64, 64)
        no_results_icon.setStyleSheet(f"""
            background-color: {DesignSystem.BORDER_LIGHT};
            border-radius: 32px;
        """)
        icon_layout = QVBoxLayout(no_results_icon)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_text = QLabel("?")
        icon_text.setStyleSheet(f"""
            font-size: 28px;
            font-weight: bold;
            color: {DesignSystem.TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)
        icon_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_text)
        no_results_layout.addWidget(no_results_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        no_results_title = QLabel("No results found")
        no_results_title.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_LG};
            font-weight: bold;
            color: {DesignSystem.TEXT_PRIMARY};
            border: none;
            background: transparent;
        """)
        no_results_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results_layout.addWidget(no_results_title)

        self.no_results_desc = QLabel("Try different keywords or adjust the match threshold.")
        self.no_results_desc.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_SM};
            color: {DesignSystem.TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)
        self.no_results_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results_layout.addWidget(self.no_results_desc)

        self.results_stack.addWidget(self.no_results_widget)

        if not self.indexed_folders:
            self.results_stack.setCurrentWidget(self.empty_state)
        else:
            self.results_stack.setCurrentWidget(self.results_list)

        left_layout.addWidget(self.results_stack)
        splitter.addWidget(left_panel)

        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewCard")
        preview_frame.setStyleSheet(card_style)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)

        preview_shadow = QGraphicsDropShadowEffect()
        preview_shadow.setBlurRadius(20)
        preview_shadow.setXOffset(0)
        preview_shadow.setYOffset(2)
        preview_shadow.setColor(QColor(0, 0, 0, 25))
        preview_frame.setGraphicsEffect(preview_shadow)

        preview_header = QLabel("Preview")
        preview_header.setStyleSheet(f"""
            font-weight: 600;
            font-size: {DesignSystem.FONT_SIZE_LG};
            color: {DesignSystem.TEXT_PRIMARY};
            padding-bottom: 4px;
            border: none;
            background: transparent;
        """)
        preview_layout.addWidget(preview_header)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet(f"""
            QTextEdit {{
                border: none;
                border-radius: 8px;
                background-color: {DesignSystem.BG_SECONDARY};
                font-family: 'Menlo', 'Consolas', 'DejaVu Sans Mono', monospace;
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_PRIMARY};
                padding: 12px;
            }}
        """)
        self.preview_text.setPlaceholderText("Click a result to preview its content.")
        preview_layout.addWidget(self.preview_text)

        splitter.addWidget(preview_frame)
        splitter.setSizes([500, 400])

        return splitter

    def _setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_SECONDARY};
            }}
        """)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {DesignSystem.BORDER_LIGHT};
                text-align: center;
                font-size: {DesignSystem.FONT_SIZE_XS};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QProgressBar::chunk {{
                background-color: {DesignSystem.ACCENT_PRIMARY};
                border-radius: 4px;
            }}
        """)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setMaximumWidth(60)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.ERROR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: {DesignSystem.FONT_SIZE_XS};
            }}
            QPushButton:hover {{
                background-color: #D32F2F;
            }}
        """)
        self.cancel_btn.clicked.connect(self._cancel_indexing)

        self.status_bar.addPermanentWidget(self.cancel_btn)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = menu_bar.addMenu("Settings")

        manage_folders_action = QAction("Manage Folders", self)
        manage_folders_action.setShortcut("Ctrl+,")
        manage_folders_action.triggered.connect(self.open_settings)
        settings_menu.addAction(manage_folders_action)

        settings_menu.addSeparator()

        reindex_action = QAction("Reindex All", self)
        reindex_action.setShortcut("Ctrl+R")
        reindex_action.triggered.connect(self.start_indexing)
        settings_menu.addAction(reindex_action)

        help_menu = menu_bar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {DesignSystem.BG_PRIMARY};
                border-bottom: 1px solid {DesignSystem.BORDER_LIGHT};
                padding: 4px 10px;
                spacing: 4px;
            }}
            QToolBar::separator {{
                width: 1px;
                margin: 2px 6px;
                background-color: {DesignSystem.BORDER_LIGHT};
            }}
            QToolButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 5px;
                padding: 4px 10px;
                margin: 0 2px;
                font-size: {DesignSystem.FONT_SIZE_MD};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QToolButton:hover {{
                background-color: {DesignSystem.BG_HOVER};
                border-color: {DesignSystem.BORDER_LIGHT};
            }}
            QToolButton:pressed {{
                background-color: {DesignSystem.ACCENT_LIGHT};
            }}
        """)
        self.addToolBar(toolbar)

        add_folder_action = QAction("Add Folder", self)
        add_folder_action.triggered.connect(self._quick_add_folder)
        toolbar.addAction(add_folder_action)

        reindex_action = QAction("Reindex", self)
        reindex_action.triggered.connect(self.start_indexing)
        toolbar.addAction(reindex_action)

        toolbar.addSeparator()

        clear_cache_action = QAction("Clear Cache", self)
        clear_cache_action.triggered.connect(self._clear_search_cache)
        toolbar.addAction(clear_cache_action)

    def _setup_shortcuts(self):
        focus_search = QShortcut(QKeySequence("Ctrl+F"), self)
        focus_search.activated.connect(lambda: self.search_input.setFocus())

        clear_results = QShortcut(QKeySequence("Escape"), self)
        clear_results.activated.connect(self._clear_results)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {DesignSystem.BG_SECONDARY};
            }}
            QWidget {{
                background-color: {DesignSystem.BG_SECONDARY};
            }}
            QMenuBar {{
                background-color: {DesignSystem.BG_PRIMARY};
                border-bottom: 1px solid {DesignSystem.BORDER_LIGHT};
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_PRIMARY};
                padding: 4px 8px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QMenuBar::item:selected {{
                background-color: {DesignSystem.BG_HOVER};
            }}
            QMenu {{
                background-color: {DesignSystem.BG_PRIMARY};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 6px;
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QMenu::item:selected {{
                background-color: {DesignSystem.ACCENT_LIGHT};
                color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QStatusBar {{
                background-color: {DesignSystem.BG_PRIMARY};
                border-top: 1px solid {DesignSystem.BORDER_LIGHT};
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_SECONDARY};
            }}
            QSplitter {{
                background-color: transparent;
            }}
            QSplitter::handle {{
                background-color: transparent;
                width: 12px;
            }}
            QSplitter::handle:hover {{
                background-color: {DesignSystem.ACCENT_LIGHT};
                border-radius: 4px;
            }}
        """)

    def _disconnect_worker_signals(self):
        for signal, slot in self._worker_connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._worker_connections.clear()

    def _cleanup_worker(self, worker):
        if worker is None:
            return
        try:
            if worker.isRunning():
                worker.quit()
                worker.wait(2000)
            worker.deleteLater()
        except RuntimeError:
            pass

    def _on_search_mode_changed(self, index: int):
        mode = self.search_mode_combo.currentData()
        if mode == SearchMode.CONTENT and not self._content_indexing_done:
            self.search_mode_combo.setCurrentIndex(0)
            QMessageBox.information(
                self,
                "Content Indexing in Progress",
                "Content indexing is not yet complete.\n"
                "Please use filename search or wait for content indexing to finish."
            )

    def open_settings(self):
        dialog = SettingsDialog(
            self,
            self.indexed_folders.copy(),
            {k: v.copy() for k, v in self.folder_settings.items()}
        )
        if dialog.exec():
            new_folders = dialog.get_folders()
            new_folder_settings = dialog.get_folder_settings()
            folders_changed = new_folders != self.indexed_folders
            settings_changed = new_folder_settings != self.folder_settings

            if folders_changed or settings_changed:
                self.indexed_folders = new_folders
                self.folder_settings = new_folder_settings
                self._save_settings()
                self._update_results_view()

                if new_folders:
                    reply = QMessageBox.question(
                        self, "Indexing",
                        "Folders or settings have changed. Would you like to start indexing now?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.start_indexing()

    def _quick_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Index")
        if folder and folder not in self.indexed_folders:
            dialog = FolderSettingsDialog(self, folder, False, True)
            if dialog.exec():
                self.indexed_folders.append(folder)
                self.folder_settings[folder] = {
                    "include_hidden": dialog.get_include_hidden(),
                    "index_content": dialog.get_index_content()
                }
                self._save_settings()
                self.status_bar.showMessage(f"Folder added: {folder}", 3000)

                self._update_results_view()

                reply = QMessageBox.question(
                    self, "Indexing",
                    "Folder has been added. Would you like to start indexing now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.start_indexing()

    def _update_results_view(self):
        if self.indexed_folders:
            self.results_stack.setCurrentWidget(self.results_list)
        else:
            self.results_stack.setCurrentWidget(self.empty_state)

    def _load_folder_settings(self) -> dict:
        settings_str = self.settings.value("folder_settings", "{}", type=str)
        try:
            import json
            return json.loads(settings_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _save_settings(self):
        import json
        self.settings.setValue("indexed_folders", self.indexed_folders)
        self.settings.setValue("search_history", self.search_history[-50:])
        self.settings.setValue("folder_settings", json.dumps(self.folder_settings))
        self.settings.sync()

    def start_indexing(self):
        if not self.indexed_folders:
            QMessageBox.warning(
                self, "No Folders",
                "No folders to index.\nPlease add folders from the Settings menu."
            )
            return

        if self.filename_worker and self.filename_worker.isRunning():
            QMessageBox.information(self, "Indexing in Progress", "Indexing is already in progress.")
            return

        self._filename_indexing_done = False
        self._content_indexing_done = False
        self._collected_files = []

        self.search_mode_combo.setCurrentIndex(0)
        self.search_mode_combo.model().item(1).setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.cancel_btn.setVisible(True)
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.status_bar.showMessage("Scanning files...")

        self._cleanup_worker(self.filename_worker)
        self._disconnect_worker_signals()

        self.filename_worker = FilenameIndexingWorker(
            self.indexed_folders,
            self.folder_settings,
            app_service=self.app_service,
        )
        self.filename_worker.progress.connect(self.status_bar.showMessage)
        self._worker_connections.append((self.filename_worker.progress, self.status_bar.showMessage))
        self.filename_worker.file_progress.connect(self._update_indexing_progress)
        self._worker_connections.append((self.filename_worker.file_progress, self._update_indexing_progress))
        self.filename_worker.finished.connect(self._on_filename_indexing_finished)
        self._worker_connections.append((self.filename_worker.finished, self._on_filename_indexing_finished))
        self.filename_worker.cancelled.connect(self._indexing_cancelled)
        self._worker_connections.append((self.filename_worker.cancelled, self._indexing_cancelled))
        self.filename_worker.start()

    def _on_filename_indexing_finished(self):
        self._filename_indexing_done = True
        self._collected_files = self.filename_worker.get_files()

        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.indexing_status_label.setText("Filename search ready | Content indexing...")
        self.indexing_status_label.setVisible(True)

        self._cleanup_worker(self.content_worker)

        self.content_worker = ContentIndexingWorker(
            self._collected_files,
            app_service=self.app_service,
        )
        self.content_worker.progress.connect(self.status_bar.showMessage)
        self._worker_connections.append((self.content_worker.progress, self.status_bar.showMessage))
        self.content_worker.file_progress.connect(self._update_indexing_progress)
        self._worker_connections.append((self.content_worker.file_progress, self._update_indexing_progress))
        self.content_worker.finished.connect(self._on_content_indexing_finished)
        self._worker_connections.append((self.content_worker.finished, self._on_content_indexing_finished))
        self.content_worker.cancelled.connect(self._content_indexing_cancelled)
        self._worker_connections.append((self.content_worker.cancelled, self._content_indexing_cancelled))
        self.content_worker.start()

    def _on_content_indexing_finished(self):
        self._content_indexing_done = True
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setRange(0, 0)

        self.search_mode_combo.model().item(1).setEnabled(True)
        self.indexing_status_label.setText("All indexing complete")
        self.indexing_status_label.setVisible(True)
        self.status_bar.showMessage("Indexing complete", 5000)

    def _content_indexing_cancelled(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")
        self.indexing_status_label.setText("Filename search ready | Content indexing cancelled")
        self.indexing_status_label.setVisible(True)
        self.status_bar.showMessage("Content indexing has been cancelled.", 5000)

    def _cancel_indexing(self):
        if self.filename_worker and self.filename_worker.isRunning():
            self.filename_worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("Cancelling...")
        elif self.content_worker and self.content_worker.isRunning():
            self.content_worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setText("Cancelling...")

    def _indexing_cancelled(self):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.status_bar.showMessage("Indexing has been cancelled.", 5000)

    def _update_indexing_progress(self, current: int, total: int):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        mode = self.search_mode_combo.currentData()
        if mode == SearchMode.CONTENT and not self._content_indexing_done:
            QMessageBox.warning(
                self,
                "Search Unavailable",
                "Content indexing is not complete.\nPlease use filename search."
            )
            return

        if query not in self.search_history:
            self.search_history.append(query)
            self._save_settings()

        self.results_list.reset_scroll_state()
        self.preview_text.clear()
        self.status_bar.showMessage("Searching...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.search_btn.setEnabled(False)

        self._current_query = query
        self._current_mode = mode
        self._current_offset = 0
        self._fetch_size = int(self.results_count_combo.currentText())

        self._cleanup_worker(self.search_worker)

        self.search_worker = SearchWorker(
            query,
            n_results=self._fetch_size,
            mode=mode,
            app_service=self.app_service,
            offset=0,
        )
        self.search_worker.results_ready.connect(self._on_initial_results)
        self._worker_connections.append((self.search_worker.results_ready, self._on_initial_results))
        self.search_worker.error_occurred.connect(self.search_error)
        self._worker_connections.append((self.search_worker.error_occurred, self.search_error))
        self.search_worker.start()

    def _load_more_results(self) -> None:
        if not self._current_query:
            self.results_list.finish_loading(False)
            return

        self._current_offset += self._fetch_size

        self._cleanup_worker(self.search_worker)

        self.search_worker = SearchWorker(
            self._current_query,
            n_results=self._fetch_size,
            mode=self._current_mode,
            app_service=self.app_service,
            offset=self._current_offset,
        )
        self.search_worker.results_ready.connect(self._on_more_results)
        self._worker_connections.append((self.search_worker.results_ready, self._on_more_results))
        self.search_worker.error_occurred.connect(self._on_load_more_error)
        self._worker_connections.append((self.search_worker.error_occurred, self._on_load_more_error))
        self.search_worker.start()

    def _on_load_more_error(self, error_msg: str) -> None:
        self.results_list.finish_loading(False)
        self.status_bar.showMessage(f"Error loading more: {error_msg}", 5000)

    def _on_initial_results(self, results: list, has_more: bool) -> None:
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)

        if not results:
            self.no_results_desc.setText("Try different keywords or check if folders are indexed.")
            self.results_stack.setCurrentWidget(self.no_results_widget)
            self.status_bar.showMessage("No results found.", 5000)
            self.results_list.finish_loading(False)
            return

        self.results_stack.setCurrentWidget(self.results_list)
        self._display_results_batch(results, has_more, is_initial=True)

    def _on_more_results(self, results: list, has_more: bool) -> None:
        if not results:
            self.results_list.finish_loading(False)
            return

        self._display_results_batch(results, has_more, is_initial=False)

    def _display_results_batch(
        self,
        results: list,
        has_more: bool,
        is_initial: bool = False,
    ) -> None:
        min_threshold = self.threshold_combo.currentData()

        results_with_similarity = []
        for res in results:
            similarity_percent = max(0, (1 - res["distance"] / 2) * 100)
            if min_threshold == 0 or similarity_percent >= min_threshold:
                results_with_similarity.append((res, similarity_percent))

        if is_initial and not results_with_similarity:
            self.no_results_desc.setText(f"No results with {min_threshold}%+ match rate. Try lowering the threshold.")
            self.results_stack.setCurrentWidget(self.no_results_widget)
            self.status_bar.showMessage(
                f"No results with {min_threshold}%+ match rate. Try lowering the threshold.",
                5000
            )
            self.results_list.finish_loading(False)
            return

        for res, similarity in results_with_similarity:
            tier = "excellent" if similarity >= 90 else ("good" if similarity >= 80 else "other")
            self._add_result_item(res, similarity, tier=tier)

        current_count = self.results_list.count()
        status_msg = f"{current_count} results loaded"
        if has_more:
            status_msg += " (scroll for more)"
        self.status_bar.showMessage(status_msg, 5000)

        self.results_list.finish_loading(has_more)

    def _add_section_header(self, title: str, count: int, color: str):
        item = QListWidgetItem()
        widget = SectionHeaderWidget(title, count, color)
        item.setSizeHint(widget.sizeHint())
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.results_list.addItem(item)
        self.results_list.setItemWidget(item, widget)

    def _add_result_item(self, res: dict, similarity: float, tier: str = ""):
        item = QListWidgetItem()
        widget = ResultItemWidget(
            path=res["path"],
            similarity=similarity,
            snippet=res["snippet"],
            file_type=res.get("type", "unknown"),
            tier=tier
        )
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, res)
        item.setToolTip(res["path"])
        self.results_list.addItem(item)
        self.results_list.setItemWidget(item, widget)

    def search_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.search_btn.setEnabled(True)
        self.status_bar.showMessage(f"Error: {error_msg}")
        QMessageBox.critical(self, "Search Error", error_msg)

    def _show_preview(self, item: QListWidgetItem):
        result_data = item.data(Qt.ItemDataRole.UserRole)
        if not result_data:
            return

        file_path = result_data.get("path", "")
        snippet = result_data.get("snippet", "")

        try:
            if file_path.lower().endswith((".txt", ".md", ".py", ".json", ".csv")):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()[:5000]
                    self.preview_text.setPlainText(content)
            else:
                self.preview_text.setPlainText(
                    f"File: {file_path}\n\n--- Snippet ---\n{snippet}"
                )
        except Exception as e:
            self.preview_text.setPlainText(
                f"Cannot read file: {e}\n\n--- Snippet ---\n{snippet}"
            )

    def _open_file_from_result(self, item: QListWidgetItem):
        file_path = item.toolTip()
        if file_path and os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(
                self, "File Not Found", f"Cannot find file:\n{file_path}"
            )

    def _clear_results(self):
        self.results_list.reset_scroll_state()
        self._current_query = ""
        self._current_offset = 0
        self.preview_text.clear()
        self.status_bar.clearMessage()

    def _clear_search_cache(self):
        self.status_bar.showMessage("Search cache has been cleared.", 3000)

    def _show_about(self):
        QMessageBox.about(
            self,
            "Local Semantic Explorer",
            "<h3>Local Semantic Explorer</h3>"
            "<p>AI-powered semantic search for local files.</p>"
            "<p><b>Search Modes:</b></p>"
            "<ul>"
            "<li>Filename: Fast search (by filename)</li>"
            "<li>Content: Deep search (by file content)</li>"
            "</ul>"
            "<p><b>Supported files:</b> txt, md, py, json, csv, pdf, png, jpg, jpeg, webp</p>"
            "<p><b>Tech:</b> Ollama (nomic-embed-text), ChromaDB</p>"
            "<hr>"
            "<p>2024 L4MOLE Search</p>"
        )

    def closeEvent(self, event):
        self._disconnect_worker_signals()

        if self.filename_worker and self.filename_worker.isRunning():
            self.filename_worker.cancel()
            self.filename_worker.wait(5000)

        if self.content_worker and self.content_worker.isRunning():
            self.content_worker.cancel()
            self.content_worker.wait(5000)

        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait(2000)

        self._cleanup_worker(self.filename_worker)
        self._cleanup_worker(self.content_worker)
        self._cleanup_worker(self.search_worker)

        self.filename_worker = None
        self.content_worker = None
        self.search_worker = None

        from ...infrastructure.di import AppInjector
        AppInjector.reset_instance()

        self._save_settings()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
