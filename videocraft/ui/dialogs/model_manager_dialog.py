"""Model manager dialog — download, verify, and delete ML model weights."""

from __future__ import annotations

import logging
from pathlib import Path

import requests
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
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from videocraft.core.hf_auth import AUTH_STATUSES, auth_headers, is_hf_url
from videocraft.core.models_registry import (
    MISMATCH,
    MODELS,
    UNVERIFIED,
    VERIFIED,
    get_models_dir,
    model_path,
    verify_model,
    verify_sha256,
)
from videocraft.core.theme import mark_hint

logger = logging.getLogger(__name__)

# Stable row order for the table
_MODEL_KEYS: list[str] = list(MODELS.keys())


class _DownloadWorker(QThread):
    """Background thread for downloading model files.

    Downloads to <dest>.part and renames on success so cancelled or failed
    downloads never show up as installed models. Cancellation is
    cooperative (checked between chunks) — never QThread.terminate().
    """

    progress = pyqtSignal(int, int)  # downloaded_bytes, total_bytes
    download_ok = pyqtSignal(str)  # filepath on success
    download_error = pyqtSignal(str)  # error message ("" for user cancel)

    def __init__(self, url: str, dest: Path, sha256: str | None = None) -> None:
        super().__init__()
        self.url = url
        self.dest = dest
        self.sha256 = sha256
        self._cancelled = False
        self.auth_status: int | None = None  # set when a token may fix the failure

    def cancel(self) -> None:
        """Request cooperative cancellation."""
        self._cancelled = True

    def run(self) -> None:
        part = self.dest.with_name(self.dest.name + ".part")
        try:
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            resp = requests.get(
                self.url, stream=True, timeout=60, headers=auth_headers(self.url)
            )
            if resp.status_code in AUTH_STATUSES and is_hf_url(self.url):
                self.auth_status = resp.status_code
                self.download_error.emit(
                    f"Hugging Face refused the download (HTTP {resp.status_code})."
                )
                return
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    if self._cancelled:
                        f.close()
                        part.unlink(missing_ok=True)
                        self.download_error.emit("")  # silent: user cancelled
                        return
                    f.write(chunk)
                    downloaded += len(chunk)
                    self.progress.emit(downloaded, total)

            if not verify_sha256(part, self.sha256):
                part.unlink(missing_ok=True)
                self.download_error.emit(
                    "The downloaded file did not match its expected checksum and was discarded. "
                    "The upstream file may have changed — please report it on the VideoCraft issue tracker."
                )
                return

            part.rename(self.dest)
            self.download_ok.emit(str(self.dest))

        except (requests.RequestException, OSError) as e:
            part.unlink(missing_ok=True)
            self.download_error.emit(str(e))


class _VerifyWorker(QThread):
    """Re-hashes the installed models in the background."""

    result = pyqtSignal(str, str, str)  # key, status, sha256

    def __init__(self, keys: list[str]) -> None:
        super().__init__()
        self._keys = keys
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for key in self._keys:
            if self._cancelled:
                return
            status, digest = verify_model(key, is_cancelled=lambda: self._cancelled)
            if not self._cancelled:
                self.result.emit(key, status, digest)


class ModelManagerDialog(QDialog):
    """Model download manager.

    Shows all registry models with status, size, and download/delete
    actions. Demucs (vocal remover) manages its own weights and is not
    listed.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Manager")
        self.setMinimumSize(650, 450)
        self._models_dir = get_models_dir()
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._workers: list[_DownloadWorker] = []
        self._download_queue: list[str] = []  # keys pending in Download All
        self._verify_results: dict[str, tuple[str, str]] = {}  # key → (status, sha256)
        self._verify_worker: _VerifyWorker | None = None
        self._setup_ui()
        self._populate_table()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            f"Manage AI model weights. Models are downloaded to {self._models_dir}. "
            "The vocal remover (Demucs) downloads its own weights "
            "automatically on first use."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 4px;")
        mark_hint(info, True)
        layout.addWidget(info)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Model", "Tool", "Status", "Size", ""])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 100)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_verify = QPushButton("Verify Installed")
        self.btn_verify.setToolTip("Re-check the downloaded models against their expected checksums")
        self.btn_verify.clicked.connect(self._verify_installed)
        btn_layout.addWidget(self.btn_verify)

        self.btn_download_all = QPushButton("Download All Missing")
        self.btn_download_all.clicked.connect(self._download_all)
        btn_layout.addWidget(self.btn_download_all)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _populate_table(self) -> None:
        """Fill the table with model info."""
        self.table.setRowCount(len(_MODEL_KEYS))

        for i, key in enumerate(_MODEL_KEYS):
            model = MODELS[key]
            filepath = model_path(key)
            exists = filepath.exists()

            self.table.setItem(i, 0, QTableWidgetItem(model["display"]))
            self.table.setItem(i, 1, QTableWidgetItem(model["tool"]))

            status_text = "✓ Downloaded" if exists else "✗ Missing"
            status_color = "#4ec9b0" if exists else "#f44747"
            tooltip = ""
            if exists and key in self._verify_results:
                check, digest = self._verify_results[key]
                tooltip = f"SHA-256: {digest}" if digest else ""
                if check == VERIFIED:
                    status_text = "✓ Verified"
                elif check == MISMATCH:
                    status_text, status_color = "✗ Corrupt or modified", "#f44747"
                    tooltip += "\nThis file does not match the expected checksum — delete it and download again."
                elif check == UNVERIFIED:
                    status_text = "✓ Downloaded (no reference checksum)"
            status_item = QTableWidgetItem(status_text)
            status_item.setToolTip(tooltip)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, status_item)

            if exists:
                size_mb = filepath.stat().st_size / (1024 * 1024)
                size_text = f"{size_mb:.1f} MB"
            else:
                size_text = f"~{model['size_mb']} MB"
            self.table.setItem(i, 3, QTableWidgetItem(size_text))

            btn = QPushButton("Delete" if exists else "Download")
            # Bind the key at definition time — a late-binding lambda would
            # make every button act on the last row.
            btn.clicked.connect(lambda _=False, k=key: self._on_action(k))
            self.table.setCellWidget(i, 4, btn)

    def _verify_installed(self) -> None:
        """Hash every installed model in the background and show the results."""
        keys = [k for k in _MODEL_KEYS if model_path(k).exists()]
        if not keys:
            QMessageBox.information(self, "Nothing to verify", "No models are downloaded yet.")
            return
        self.btn_verify.setEnabled(False)
        self.btn_verify.setText("Verifying…")
        self._verify_results.clear()
        worker = _VerifyWorker(keys)
        worker.result.connect(self._on_verify_result)
        worker.finished.connect(self._on_verify_done)
        self._verify_worker = worker
        worker.start()

    def _on_verify_result(self, key: str, status: str, digest: str) -> None:
        self._verify_results[key] = (status, digest)
        self._populate_table()

    def _on_verify_done(self) -> None:
        self.btn_verify.setEnabled(True)
        self.btn_verify.setText("Verify Installed")
        bad = [MODELS[k]["display"] for k, (s, _d) in self._verify_results.items() if s == MISMATCH]
        if bad:
            QMessageBox.warning(
                self, "Verification failed",
                "These models do not match their expected checksums. Delete and download them again:\n\n"
                + "\n".join(bad),
            )

    def _on_action(self, key: str) -> None:
        """Handle download or delete action for a model."""
        filepath = model_path(key)
        if filepath.exists():
            self._delete_model(key, filepath)
        else:
            self._download_model(key)

    def _start_download(self, key: str, on_done) -> None:
        """Start a download worker with a progress dialog.

        on_done(error_msg | None) is called exactly once when the download
        ends (None = success, "" = user cancel, other = failure).
        """
        model = MODELS[key]
        filepath = model_path(key)

        progress = QProgressDialog(f"Downloading {model['display']}...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        worker = _DownloadWorker(model["urls"][0], filepath, model.get("sha256"))
        self._workers.append(worker)  # keep the QThread alive while running

        def update_progress(done: int, total: int) -> None:
            if total:
                progress.setMaximum(total)
                progress.setValue(done)

        def finish(error: str | None) -> None:
            progress.close()
            self._populate_table()
            if worker.auth_status is not None and error:
                # A Hugging Face token may fix this: guide the user, then retry once.
                from videocraft.ui.dialogs.hf_token_dialog import HFTokenDialog

                if HFTokenDialog(self, worker.auth_status).exec() == QDialog.DialogCode.Accepted:
                    self._start_download(key, on_done)
                    return
            on_done(error)

        worker.progress.connect(update_progress)
        worker.download_ok.connect(lambda _path: finish(None))
        worker.download_error.connect(finish)
        worker.finished.connect(lambda w=worker: self._workers.remove(w) if w in self._workers else None)
        progress.canceled.connect(worker.cancel)

        progress.show()
        worker.start()

    def _download_model(self, key: str) -> None:
        """Download a single model."""
        model = MODELS[key]

        def on_done(error: str | None) -> None:
            if error:  # "" = user cancel → no dialog
                QMessageBox.critical(
                    self, "Download Failed",
                    f"Could not download {model['display']}:\n{error}",
                )

        self._start_download(key, on_done)

    def _delete_model(self, key: str, filepath: Path) -> None:
        """Delete a model file after confirmation."""
        model = MODELS[key]
        reply = QMessageBox.question(
            self, "Delete Model",
            f"Delete {model['display']} ({filepath.name})?\nThis file will be permanently removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            filepath.unlink(missing_ok=True)
            self._populate_table()
            logger.info("Deleted model: %s", filepath)

    def _download_all(self) -> None:
        """Download all missing models one after another (signal-driven —
        never blocks the event loop)."""
        self._download_queue = [k for k in _MODEL_KEYS if not model_path(k).exists()]
        if not self._download_queue:
            QMessageBox.information(self, "All Downloaded", "All models are already downloaded.")
            return
        self._download_next()

    def _download_next(self) -> None:
        if not self._download_queue:
            return
        key = self._download_queue.pop(0)
        model = MODELS[key]

        def on_done(error: str | None) -> None:
            if error is None:
                self._download_next()  # success → continue with the rest
            elif error == "":
                self._download_queue.clear()  # user cancelled → stop the run
            else:
                self._download_queue.clear()
                QMessageBox.critical(
                    self, "Download Failed",
                    f"Could not download {model['display']}:\n{error}\n\nDownload run stopped.",
                )

        self._start_download(key, on_done)

    def closeEvent(self, event) -> None:
        """Cancel any running downloads and wait for their threads."""
        self._download_queue.clear()
        if self._verify_worker is not None and self._verify_worker.isRunning():
            self._verify_worker.cancel()
            self._verify_worker.wait(5000)
        for worker in list(self._workers):
            worker.cancel()
        for worker in list(self._workers):
            worker.wait(5000)
        super().closeEvent(event)

    def get_total_disk_usage(self) -> str:
        """Return total disk usage of downloaded models."""
        total = 0
        for key in _MODEL_KEYS:
            filepath = model_path(key)
            if filepath.exists():
                total += filepath.stat().st_size
        if total < 1024 * 1024:
            return f"{total / 1024:.0f} KB"
        return f"{total / (1024 * 1024):.1f} MB"
