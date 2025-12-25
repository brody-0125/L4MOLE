
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .design_system import DesignSystem


class FolderSettingsDialog(QDialog):
    """Dialog for configuring settings of a single folder."""

    def __init__(
        self,
        parent=None,
        folder_path: str = "",
        include_hidden: bool = False,
        index_content: bool = True
    ):
        super().__init__(parent)
        self.setWindowTitle("Folder Settings")
        self.resize(450, 220)
        self.include_hidden = include_hidden
        self.index_content = index_content

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        folder_label = QLabel(f"Folder: {folder_path}")
        folder_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(folder_label)

        indexing_label = QLabel("Indexing Options:")
        indexing_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(indexing_label)

        self.content_checkbox = QCheckBox("Content indexing (enables file content search)")
        self.content_checkbox.setChecked(index_content)
        layout.addWidget(self.content_checkbox)

        content_hint = QLabel("Disabling content indexing allows only filename search. (Faster indexing)")
        content_hint.setStyleSheet(f"color: {DesignSystem.TEXT_SECONDARY}; font-size: {DesignSystem.FONT_SIZE_XS}; margin-left: 20px;")
        layout.addWidget(content_hint)

        self.hidden_checkbox = QCheckBox("Include hidden files (files/folders starting with .)")
        self.hidden_checkbox.setChecked(include_hidden)
        self.hidden_checkbox.setStyleSheet("margin-top: 8px;")
        layout.addWidget(self.hidden_checkbox)

        hidden_hint = QLabel("Including hidden files will also index .git, .env, etc.")
        hidden_hint.setStyleSheet(f"color: {DesignSystem.TEXT_SECONDARY}; font-size: {DesignSystem.FONT_SIZE_XS}; margin-left: 20px;")
        layout.addWidget(hidden_hint)

        layout.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_include_hidden(self) -> bool:
        return self.hidden_checkbox.isChecked()

    def get_index_content(self) -> bool:
        return self.content_checkbox.isChecked()


class SettingsDialog(QDialog):
    """Dialog for managing indexed folders and their settings."""

    def __init__(self, parent=None, current_folders=None, folder_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings - Folder Management")
        self.resize(600, 450)
        self.folders = current_folders or []
        self.folder_settings = folder_settings or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header_label = QLabel("Manage folders to index. Double-click a folder to change its settings.")
        header_label.setStyleSheet(f"color: {DesignSystem.TEXT_SECONDARY}; font-size: {DesignSystem.FONT_SIZE_SM};")
        layout.addWidget(header_label)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 8px;
                background-color: {DesignSystem.BG_PRIMARY};
                font-size: {DesignSystem.FONT_SIZE_SM};
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-bottom: 1px solid {DesignSystem.BORDER_LIGHT};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QListWidget::item:selected {{
                background-color: {DesignSystem.ACCENT_LIGHT};
                color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QListWidget::item:hover {{
                background-color: {DesignSystem.BG_HOVER};
            }}
        """)
        self.list_widget.itemDoubleClicked.connect(self._edit_folder_settings)
        self._refresh_folder_list()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_style = f"""
            QPushButton {{
                background-color: {DesignSystem.BG_PRIMARY};
                border: 1px solid {DesignSystem.BORDER_LIGHT};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: {DesignSystem.TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.BG_HOVER};
                border-color: {DesignSystem.ACCENT_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.ACCENT_LIGHT};
            }}
        """

        add_btn = QPushButton("Add Folder")
        add_btn.setMinimumHeight(36)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.ACCENT_PRIMARY};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: {DesignSystem.FONT_SIZE_SM};
                color: white;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.ACCENT_PRESSED};
            }}
        """)
        add_btn.clicked.connect(self.add_folder)

        remove_btn = QPushButton("Remove")
        remove_btn.setMinimumHeight(36)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(btn_style)
        remove_btn.clicked.connect(self.remove_folder)

        settings_btn = QPushButton("Settings")
        settings_btn.setMinimumHeight(36)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self._edit_selected_folder_settings)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(settings_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _refresh_folder_list(self):
        self.list_widget.clear()
        for folder in self.folders:
            settings = self.folder_settings.get(folder, {})
            include_hidden = settings.get("include_hidden", False)
            index_content = settings.get("index_content", True)

            display_text = folder
            tags = []
            if index_content:
                tags.append("Content")
            else:
                tags.append("Filename only")
            if include_hidden:
                tags.append("Hidden files")

            if tags:
                display_text += f"  [{', '.join(tags)}]"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            self.list_widget.addItem(item)

    def _edit_folder_settings(self, item: QListWidgetItem):
        folder = item.data(Qt.ItemDataRole.UserRole)
        if not folder:
            return

        current_settings = self.folder_settings.get(folder, {})
        include_hidden = current_settings.get("include_hidden", False)
        index_content = current_settings.get("index_content", True)

        dialog = FolderSettingsDialog(self, folder, include_hidden, index_content)
        if dialog.exec():
            self.folder_settings[folder] = {
                "include_hidden": dialog.get_include_hidden(),
                "index_content": dialog.get_index_content()
            }
            self._refresh_folder_list()

    def _edit_selected_folder_settings(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self._edit_folder_settings(current_item)
        else:
            QMessageBox.information(self, "Selection Required", "Please select a folder to configure.")

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Index")
        if folder and folder not in self.folders:
            dialog = FolderSettingsDialog(self, folder, False, True)
            if dialog.exec():
                self.folders.append(folder)
                self.folder_settings[folder] = {
                    "include_hidden": dialog.get_include_hidden(),
                    "index_content": dialog.get_index_content()
                }
                self._refresh_folder_list()

    def remove_folder(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            item = self.list_widget.item(row)
            folder = item.data(Qt.ItemDataRole.UserRole)
            self.folders.remove(folder)
            if folder in self.folder_settings:
                del self.folder_settings[folder]
            self._refresh_folder_list()

    def get_folders(self):
        return self.folders

    def get_folder_settings(self):
        return self.folder_settings
