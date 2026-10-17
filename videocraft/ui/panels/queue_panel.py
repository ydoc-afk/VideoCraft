"""Queue panel — job queue table with progress bars, status, controls."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QWidget,
    QLabel,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from videocraft.core.job import Job
from videocraft.core.job_queue import JobQueue

logger = logging.getLogger(__name__)

# Status → color mapping
_STATUS_COLORS = {
    "queued": "#888888",
    "running": "#e85d04",
    "done": "#4ec9b0",
    "failed": "#f44747",
    "cancelled": "#666666",
}


class _ProgressBarItem(QWidget):
    """Progress bar widget for table cells."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self.bar = QProgressBar()
        self.bar.setFixedHeight(14)
        self.bar.setTextVisible(True)
        self.bar.setValue(0)
        layout.addWidget(self.bar, 1)

    def set_progress(self, value: float) -> None:
        """Set progress 0.0–1.0."""
        self.bar.setValue(int(value * 100))

    def set_status(self, status: str) -> None:
        """Set status text and color."""
        color = _STATUS_COLORS.get(status, "#888888")
        self.bar.setFormat(f"[{status.upper()}] %p%")
        palette = self.bar.palette()
        palette.setColor(palette.ColorRole.Highlight, QColor(color))
        self.bar.setPalette(palette)


class QueuePanel(QFrame):
    """Queue panel — job table with progress, status, and controls."""

    # Signals for user actions
    add_requested = pyqtSignal()
    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, queue: JobQueue, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.queue = queue
        self._row_map: dict[str, int] = {}  # job_id → row index
        self._jobs: dict[str, Job] = {}  # job_id → Job
        self._setup_ui()

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.setInterval(500)  # 500ms refresh
        self._timer.timeout.connect(self._refresh_table)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Filename", "Tool", "Status", "Progress", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 60)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        # Control buttons
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("＋ Add to Queue")
        self.btn_add.setToolTip("Add the files selected in the Source panel using the active tool tab")
        self.btn_add.clicked.connect(self.add_requested.emit)
        btn_layout.addWidget(self.btn_add)

        self.btn_start = QPushButton("▶ Start Queue")
        self.btn_start.clicked.connect(self._on_start)
        btn_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_pause.setEnabled(False)
        btn_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("✕ Cancel")
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_clear = QPushButton("Clear Completed")
        self.btn_clear.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.btn_clear)

        layout.addLayout(btn_layout)

    def add_job(self, job: Job) -> None:
        """Add a job to the table display."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._row_map[job.id] = row
        self._jobs[job.id] = job

        # Filename
        self.table.setItem(row, 0, QTableWidgetItem(job.source_path.name))

        # Tool
        self.table.setItem(row, 1, QTableWidgetItem(", ".join(job.pipeline)))

        # Status
        status_item = QTableWidgetItem(job.status.upper())
        status_item.setForeground(QColor(_STATUS_COLORS.get(job.status, "#888888")))
        self.table.setItem(row, 2, status_item)

        # Progress bar
        progress_widget = _ProgressBarItem()
        progress_widget.set_status(job.status)
        self.table.setCellWidget(row, 3, progress_widget)

        # Cancel button
        cancel_btn = QPushButton("✕")
        cancel_btn.setProperty("job_id", job.id)
        cancel_btn.clicked.connect(lambda: self.queue.cancel(job.id))
        self.table.setCellWidget(row, 4, cancel_btn)

    def _refresh_table(self) -> None:
        """Refresh table from queue state."""
        for job_id, row in self._row_map.items():
            job = self._jobs.get(job_id)
            if job is None or row >= self.table.rowCount():
                continue

            # Update status
            status_item = self.table.item(row, 2)
            if status_item:
                status_item.setText(job.status.upper())
                status_item.setForeground(QColor(_STATUS_COLORS.get(job.status, "#888888")))

            # Update progress bar
            widget = self.table.cellWidget(row, 3)
            if isinstance(widget, _ProgressBarItem):
                widget.set_progress(job.progress)
                widget.set_status(job.status)

    def start_timer(self) -> None:
        """Start the auto-refresh timer."""
        self._timer.start()
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)

    def stop_timer(self) -> None:
        """Stop the auto-refresh timer (after one final refresh)."""
        self._timer.stop()
        self._refresh_table()  # render final statuses
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)

    def selected_job_ids(self) -> list[str]:
        """Return job IDs for the currently selected table rows."""
        selection = self.table.selectionModel()
        if selection is None:
            return []
        rows = {index.row() for index in selection.selectedRows()}
        return [job_id for job_id, row in self._row_map.items() if row in rows]

    # Buttons only emit — MainWindow owns queue state and drives the
    # refresh timer (starting may be vetoed by pre-flight; pausing must
    # keep refreshing while running jobs drain).
    def _on_start(self) -> None:
        self.start_requested.emit()

    def _on_pause(self) -> None:
        self.pause_requested.emit()

    def _on_cancel(self) -> None:
        self.cancel_requested.emit()

    def clear_completed(self) -> None:
        """Remove finished jobs from the queue and rebuild the table."""
        self._on_clear()

    def _on_clear(self) -> None:
        self.queue.clear_completed()
        # Rebuild table
        self.table.setRowCount(0)
        self._row_map.clear()
        self._jobs.clear()
        for job in self.queue.jobs:
            self.add_job(job)
