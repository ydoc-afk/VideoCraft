"""Log panel — QPlainTextEdit with auto-scroll, clear button, severity coloring."""

from __future__ import annotations

import html

from PyQt6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt


LOG_COLORS: dict[str, str] = {
    "INFO": "#d4d4d4",
    "WARNING": "#f0a500",
    "ERROR": "#f44747",
    "SUCCESS": "#4ec9b0",
    "FRAME": "#9cdcfe",
}


class LogPanel(QWidget):
    """Log display widget with colored severity levels and auto-scroll."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log text area
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setObjectName("logPanel")
        self.log_edit.setTabChangesFocus(True)
        # Frame-based jobs log one line per frame — cap the document so
        # long runs don't grow memory without bound.
        self.log_edit.setMaximumBlockCount(5000)
        layout.addWidget(self.log_edit, 1)

        # Clear button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_log)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

    def append_log(self, line: str) -> None:
        """Append a log line with severity-based coloring."""
        color = self._detect_color(line)
        # Escape user-controlled content (filenames with <, &, …) — this
        # goes through appendHtml.
        safe = html.escape(line)
        self.log_edit.appendHtml(f'<span style="color:{color};">{safe}</span>')
        # Auto-scroll to bottom
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )

    def clear_log(self) -> None:
        """Clear all log content."""
        self.log_edit.clear()

    @staticmethod
    def _detect_color(line: str) -> str:
        """Detect severity level from log line and return color hex.

        Prefers the "[LEVEL]" prefix convention; falls back to a substring
        match so free-form lines still get a reasonable color.
        """
        upper = line.upper()
        for level, color in LOG_COLORS.items():
            if upper.startswith(f"[{level}]"):
                return color
        for level, color in LOG_COLORS.items():
            if level in upper:
                return color
        return LOG_COLORS["INFO"]
