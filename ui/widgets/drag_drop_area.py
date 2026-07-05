"""Drag-and-drop area — accepts video/audio files dropped onto the widget."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QPalette

logger = logging.getLogger(__name__)

# Accepted file extensions
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"}
_AUDIO_EXTS = {".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"}
_ALL_EXTS = _VIDEO_EXTS | _AUDIO_EXTS


class DragDropArea(QFrame):
    """Drag-and-drop area that accepts video and audio files.

    Emits files_dropped signal with list of Path objects when files are dropped.
    Shows visual feedback (highlight border) when valid files are dragged over it.

    Usage:
        area = DragDropArea()
        area.files_dropped.connect(self._handle_files)
        layout.addWidget(area)
    """

    files_dropped = pyqtSignal(list)  # list[Path]

    def __init__(self, title: str = "Drop files here", parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._hovering = False
        self._title = title
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Compact single-line icon + title, with a smaller hint below.
        self.label_icon = QLabel("📁")
        self.label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_icon.setStyleSheet("font-size: 22px; color: #888;")
        layout.addWidget(self.label_icon)

        # Title
        self.label_title = QLabel(self._title)
        self.label_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_title.setStyleSheet("color: #888;")
        layout.addWidget(self.label_title)

        # Hint
        self.label_hint = QLabel("MP4, MKV, MOV, AVI, WebM, MP3, WAV, FLAC…")
        self.label_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_hint.setStyleSheet("color: #555; font-size: 10px;")
        layout.addWidget(self.label_hint)

        # Default style
        self.setStyleSheet("""
            DragDropArea {
                border: 2px dashed #444;
                border-radius: 8px;
                background-color: #1a1a1a;
            }
        """)

    def _set_hover(self, hovering: bool) -> None:
        """Update visual state for drag hover."""
        if self._hovering == hovering:
            return
        self._hovering = hovering
        color = "#e85d04" if hovering else "#444"
        bg = "#2a2018" if hovering else "#1a1a1a"
        self.setStyleSheet(f"""
            DragDropArea {{
                border: 2px dashed {color};
                border-radius: 8px;
                background-color: {bg};
            }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Check if dragged files are acceptable."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            has_valid = any(
                Path(u.toLocalFile()).suffix.lower() in _ALL_EXTS
                for u in urls
            )
            if has_valid:
                event.acceptProposedAction()
                self._set_hover(True)

    def dragMoveEvent(self, event) -> None:
        """Handle drag move (keep hover state)."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        """Handle drag leave (remove hover highlight)."""
        self._set_hover(False)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle file drop — emit list of valid file paths."""
        self._set_hover(False)

        files: list[Path] = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in _ALL_EXTS and path.exists():
                files.append(path)

        if files:
            self.files_dropped.emit(files)
            self.label_title.setText(f"{len(files)} file(s) dropped")
            self.label_title.setStyleSheet("color: #4ec9b0; padding: 4px;")
            # Reset after a moment
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.label_title.setText(self._title))

    def set_title(self, title: str) -> None:
        """Update the drop area title."""
        self._title = title
        self.label_title.setText(title)
