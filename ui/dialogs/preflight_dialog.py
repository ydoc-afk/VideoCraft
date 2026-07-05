"""Pre-flight dialog — checks FFmpeg, models, CUDA, disk space."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon

from core.job import Job

logger = logging.getLogger(__name__)

# Check name → icon/color mapping
_CHECK_COLORS = {
    "PASS": "#4ec9b0",
    "WARN": "#e8a000",
    "FAIL": "#f44747",
}


class PreflightChecker:
    """Runs pre-flight checks for a job."""

    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        from core.ffmpeg import ffmpeg_cmd
        try:
            result = subprocess.run(
                [ffmpeg_cmd(), "-version"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def check_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def check_disk_space(self, job: Job) -> bool:
        """Check if there's enough disk space for the output."""
        try:
            source_size = job.source_path.stat().st_size if job.source_path.exists() else 0
            # ML tools can produce larger outputs (upscaler 2x = 4x size)
            scale = 4 if "upscaler" in job.pipeline else 2
            estimated_output = source_size * scale

            output_dir = job.output_path.parent
            if output_dir.exists():
                import shutil
                disk_free = shutil.disk_usage(str(output_dir)).free
                return disk_free > estimated_output * 1.5  # 50% buffer
            return True  # Can't check, assume OK
        except OSError:
            return True

    def check_models(self, job: Job) -> bool:
        """Check if required models exist for the job's pipeline.

        Resolves through the canonical model registry so the check agrees
        with the Model Manager and the processors. Tools without registry
        entries (converter, hdr, upmixer, vocal_remover/Demucs) need none.
        """
        from core.models_registry import find_model, keys_for_tool

        for tool in job.pipeline:
            keys = keys_for_tool(tool)
            if not keys:
                continue
            if not any(find_model(k) for k in keys):
                return False
        return True


class _CheckWorker(QThread):
    """Background thread that runs pre-flight checks."""

    check_result = pyqtSignal(str, str, str)  # name, status, message

    def __init__(self, job: Job) -> None:
        super().__init__()
        self.job = job
        self.checker = PreflightChecker()

    def run(self) -> None:
        """Run all checks and emit results."""
        # FFmpeg
        if self.checker.check_ffmpeg():
            self.check_result.emit("FFmpeg", "PASS", "Found on PATH")
        else:
            self.check_result.emit("FFmpeg", "FAIL", "Not found — required for all tools")

        # CUDA
        if self.checker.check_cuda():
            self.check_result.emit("CUDA", "PASS", "GPU available for ML tools")
        else:
            has_ml = any(t in ("upscaler", "denoiser", "colorizer") for t in self.job.pipeline)
            status = "WARN" if has_ml else "PASS"
            msg = "CPU-only (slow for ML)" if has_ml else "CPU-only (OK for converter)"
            self.check_result.emit("CUDA", status, msg)

        # Disk space
        if self.checker.check_disk_space(self.job):
            self.check_result.emit("Disk Space", "PASS", "Sufficient space available")
        else:
            self.check_result.emit("Disk Space", "FAIL", "Insufficient disk space")

        # Models
        if self.checker.check_models(self.job):
            self.check_result.emit("Models", "PASS", "All required models present")
        else:
            has_ml = any(t in ("upscaler", "denoiser", "colorizer") for t in self.job.pipeline)
            if has_ml:
                self.check_result.emit("Models", "WARN", "Some models missing — will download")
            else:
                self.check_result.emit("Models", "PASS", "No models needed")


class PreflightDialog(QDialog):
    """Pre-flight check dialog.

    Shows a table of checks with PASS/WARN/FAIL status.
    Blocks until user confirms or cancels.
    """

    def __init__(self, job: Job, parent=None) -> None:
        super().__init__(parent)
        self.job = job
        self.setWindowTitle("Pre-flight Check")
        self.setMinimumSize(500, 300)
        self._all_pass = True
        self._has_warnings = False
        self._models_missing = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Running pre-flight checks..."))

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Check", "Status", "Details"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results_table, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_download = QPushButton("Download Missing Models")
        self.btn_download.clicked.connect(self._on_download)
        self.btn_download.setVisible(False)
        btn_layout.addWidget(self.btn_download)

        self.btn_proceed = QPushButton("Proceed")
        self.btn_proceed.clicked.connect(self.accept)
        self.btn_proceed.setEnabled(False)
        btn_layout.addWidget(self.btn_proceed)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _run_checks(self) -> None:
        """Run pre-flight checks in background."""
        existing = getattr(self, "worker", None)
        if existing is not None and existing.isRunning():
            existing.wait(8000)
        self.worker = _CheckWorker(self.job)
        self.worker.check_result.connect(self._on_check_result)
        self.worker.finished.connect(self._on_checks_done)
        self.worker.start()

    def _on_check_result(self, name: str, status: str, message: str) -> None:
        """Handle a single check result."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        self.results_table.setItem(row, 0, QTableWidgetItem(name))

        status_item = QTableWidgetItem(status)
        color = _CHECK_COLORS.get(status, "#888888")
        status_item.setForeground(QColor(color))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_table.setItem(row, 1, status_item)

        self.results_table.setItem(row, 2, QTableWidgetItem(message))

        if status == "FAIL":
            self._all_pass = False
        elif status == "WARN":
            self._has_warnings = True
        if name == "Models" and status != "PASS":
            self._models_missing = True

    def _on_checks_done(self) -> None:
        """Enable proceed button after all checks complete."""
        self.btn_proceed.setEnabled(True)

        if self._models_missing:
            self.btn_download.setVisible(True)

    def _on_download(self) -> None:
        """Open the Model Manager, then re-run the checks."""
        from ui.dialogs.model_manager_dialog import ModelManagerDialog

        dialog = ModelManagerDialog(self)
        dialog.exec()

        # Re-run checks against the (possibly) newly downloaded models
        self.results_table.setRowCount(0)
        self._all_pass = True
        self._has_warnings = False
        self._models_missing = False
        self.btn_proceed.setEnabled(False)
        self.btn_download.setVisible(False)
        self._run_checks()

    def exec(self) -> int:
        """Run the dialog and return result."""
        self._run_checks()
        return super().exec()

    def done(self, result: int) -> None:
        """Wait for the check thread before the dialog is destroyed."""
        worker = getattr(self, "worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(8000)
        super().done(result)
