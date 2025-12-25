
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .design_system import DesignSystem


class InfiniteScrollListWidget(QListWidget):
    """QListWidget with infinite scroll support."""

    load_more_requested = pyqtSignal()

    SCROLL_THRESHOLD = 0.85

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._has_more = True
        self._loading_item: QListWidgetItem | None = None

        self.setAlternatingRowColors(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background-color: transparent;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {DesignSystem.BORDER_LIGHT};
                padding: 4px;
                margin: 0;
            }}
            QListWidget::item:selected {{
                background-color: {DesignSystem.ACCENT_LIGHT};
                border-radius: 6px;
            }}
            QListWidget::item:hover {{
                background-color: {DesignSystem.BG_HOVER};
                border-radius: 6px;
            }}
        """)

        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, value: int) -> None:
        if self._loading or not self._has_more:
            return

        scrollbar = self.verticalScrollBar()
        max_value = scrollbar.maximum()

        if max_value <= 0:
            return

        scroll_ratio = value / max_value
        if scroll_ratio >= self.SCROLL_THRESHOLD:
            self._request_more()

    def _request_more(self) -> None:
        if self._loading or not self._has_more:
            return

        self._loading = True
        self._show_loading_indicator()
        self.load_more_requested.emit()

    def _show_loading_indicator(self) -> None:
        if self._loading_item is not None:
            return

        self._loading_item = QListWidgetItem()
        self._loading_item.setFlags(Qt.ItemFlag.NoItemFlags)

        loading_widget = QWidget()
        layout = QHBoxLayout(loading_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setFixedSize(120, 4)
        progress.setTextVisible(False)
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {DesignSystem.BG_SECONDARY};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {DesignSystem.ACCENT_PRIMARY};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(progress)

        self._loading_item.setSizeHint(loading_widget.sizeHint())
        self.addItem(self._loading_item)
        self.setItemWidget(self._loading_item, loading_widget)

    def _hide_loading_indicator(self) -> None:
        if self._loading_item is not None:
            row = self.row(self._loading_item)
            if row >= 0:
                self.takeItem(row)
            self._loading_item = None

    def finish_loading(self, has_more: bool) -> None:
        self._hide_loading_indicator()
        self._loading = False
        self._has_more = has_more

    def reset_scroll_state(self) -> None:
        self._loading = False
        self._has_more = True
        self._hide_loading_indicator()
        self.clear()

    @property
    def is_loading(self) -> bool:
        return self._loading

    @property
    def has_more(self) -> bool:
        return self._has_more


class EmptyStateWidget(QWidget):
    """Widget displayed when no folders are indexed."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        icon_container = QFrame()
        icon_container.setFixedSize(80, 80)
        icon_container.setStyleSheet(f"""
            background-color: {DesignSystem.ACCENT_LIGHT};
            border-radius: 40px;
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel("+")
        icon_label.setStyleSheet(f"""
            font-size: 36px;
            font-weight: 300;
            color: {DesignSystem.ACCENT_PRIMARY};
            border: none;
            background: transparent;
        """)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_container, alignment=Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel("Add a folder to search")
        title_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_XL};
            font-weight: bold;
            color: {DesignSystem.TEXT_PRIMARY};
            border: none;
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        desc_label = QLabel("Add folders to search files by name or content using AI.")
        desc_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_SM};
            color: {DesignSystem.TEXT_SECONDARY};
            border: none;
            background: transparent;
        """)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        self.add_btn = QPushButton("+ Add Folder")
        self.add_btn.setMinimumSize(160, 44)
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DesignSystem.ACCENT_PRIMARY};
                color: white;
                border: none;
                border-radius: 22px;
                font-size: {DesignSystem.FONT_SIZE_LG};
                font-weight: bold;
                padding: 12px 24px;
            }}
            QPushButton:hover {{
                background-color: {DesignSystem.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {DesignSystem.ACCENT_PRESSED};
            }}
        """)
        layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        hint_label = QLabel("Or click 'Add Folder' in the toolbar above")
        hint_label.setStyleSheet(f"""
            font-size: {DesignSystem.FONT_SIZE_XS};
            color: {DesignSystem.TEXT_SECONDARY};
            margin-top: 8px;
            border: none;
            background: transparent;
        """)
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        layout.addStretch()


class ResultItemWidget(QWidget):
    """Widget for displaying a single search result item."""

    def __init__(self, path: str, similarity: float, snippet: str, file_type: str, tier: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        ext = os.path.splitext(path)[1].lower()
        ext_colors = {
            '.py': '#3776AB', '.js': '#F7DF1E', '.ts': '#3178C6',
            '.json': '#292929', '.md': '#083FA1', '.txt': '#666666',
            '.html': '#E34F26', '.css': '#1572B6', '.pdf': '#FF0000',
        }
        ext_color = ext_colors.get(ext, DesignSystem.ACCENT_PRIMARY)

        file_icon = QLabel(ext[1:3].upper() if ext else "F")
        file_icon.setFixedSize(24, 24)
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setStyleSheet(f"""
            background-color: {ext_color};
            color: white;
            border-radius: 4px;
            font-size: 9px;
            font-weight: bold;
        """)
        header_layout.addWidget(file_icon)

        file_name = os.path.basename(path)
        name_label = QLabel(file_name)
        name_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: {DesignSystem.FONT_SIZE_MD};
            color: {DesignSystem.TEXT_PRIMARY};
        """)
        header_layout.addWidget(name_label)

        if tier == "excellent":
            tier_label = QLabel("TOP")
            tier_label.setToolTip("90%+ match")
            tier_label.setStyleSheet(f"""
                background-color: #FFD700;
                color: #333;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 9px;
                font-weight: bold;
            """)
            header_layout.addWidget(tier_label)

        header_layout.addStretch()

        type_label = QLabel(file_type.upper())
        type_label.setStyleSheet(f"""
            background-color: {DesignSystem.ACCENT_LIGHT};
            color: {DesignSystem.ACCENT_PRIMARY};
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        """)
        header_layout.addWidget(type_label)

        similarity_color = self._get_similarity_color(similarity)
        similarity_label = QLabel(f"{similarity:.1f}%")
        similarity_label.setStyleSheet(f"""
            background-color: {similarity_color};
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        """)
        header_layout.addWidget(similarity_label)

        layout.addLayout(header_layout)

        path_label = QLabel(os.path.dirname(path))
        path_label.setStyleSheet(f"""
            color: {DesignSystem.TEXT_SECONDARY};
            font-size: {DesignSystem.FONT_SIZE_XS};
        """)
        path_label.setToolTip(os.path.dirname(path))
        path_label.setMaximumWidth(400)
        layout.addWidget(path_label)

        if snippet:
            snippet_label = QLabel(snippet)
            snippet_label.setStyleSheet(f"""
                color: {DesignSystem.TEXT_SECONDARY};
                font-size: {DesignSystem.FONT_SIZE_SM};
                margin-top: 2px;
            """)
            snippet_label.setWordWrap(True)
            snippet_label.setMaximumHeight(40)
            layout.addWidget(snippet_label)

    def _get_similarity_color(self, similarity: float) -> str:
        if similarity >= 90:
            return "#2E7D32"
        elif similarity >= 80:
            return "#4CAF50"
        elif similarity >= 60:
            return "#FF9800"
        elif similarity >= 40:
            return "#FFC107"
        else:
            return "#9E9E9E"


class SectionHeaderWidget(QWidget):
    """Widget for displaying a section header in results list."""

    def __init__(self, title: str, count: int, color: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        indicator = QFrame()
        indicator.setFixedSize(4, 16)
        indicator.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(indicator)

        title_label = QLabel(f"{title}")
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {DesignSystem.FONT_SIZE_SM};
            color: {DesignSystem.TEXT_PRIMARY};
            background: transparent;
        """)
        layout.addWidget(title_label)

        count_label = QLabel(f"{count}")
        count_label.setStyleSheet(f"""
            color: {DesignSystem.TEXT_SECONDARY};
            font-size: {DesignSystem.FONT_SIZE_XS};
            background: transparent;
        """)
        layout.addWidget(count_label)

        layout.addStretch()

        self.setStyleSheet(f"background-color: {DesignSystem.BG_SECONDARY}; border-radius: 6px;")
