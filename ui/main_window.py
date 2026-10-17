"""Main window — QMainWindow with splitter layout, panels, menu bar."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMainWindow,
    QSplitter,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent

from core.config import AppConfig
from core.job import Job
from core.job_queue import JobQueue, is_ml_job
from core.worker import Worker
from ui.panels.log_panel import LogPanel
from ui.panels.source_panel import SourcePanel
from ui.panels.output_panel import OutputPanel
from ui.panels.queue_panel import QueuePanel
from ui.panels.tools_panel import ToolsPanel
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.model_manager_dialog import ModelManagerDialog

logger = logging.getLogger(__name__)

# Accepted file extensions for drag-and-drop on the main window
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"}
_AUDIO_EXTS = {".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"}
_ALL_EXTS = _VIDEO_EXTS | _AUDIO_EXTS


def _try_qtawesome():
    """Try to import qtawesome for icons. Returns None if unavailable."""
    try:
        import qtawesome as qta
        return qta
    except ImportError:
        return None


def _icon(qta, name: str, color: str = "#e85d04"):
    """Safely get a qtawesome icon, returning None if unavailable."""
    if qta is not None:
        return qta.icon(name, color=color)
    return None


class MainWindow(QMainWindow):
    """Main application window with HandBrake-style layout."""

    def __init__(self, ffmpeg_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.ffmpeg_path = ffmpeg_path
        self.setWindowTitle("VideoCraft — AI Video Enhancement")
        self.setMinimumSize(QSize(1100, 700))
        self.setAcceptDrops(True)

        # Load config
        config_path = AppConfig.platform_config_path()
        self.config = AppConfig.load(config_path)
        logger.info("Config loaded from %s", config_path)

        # Core components
        self.queue = JobQueue(concurrent_jobs=self.config.general.concurrent_jobs)
        self._workers: dict[str, Worker] = {}
        self._queue_active = False  # dispatching enabled (False = paused/stopped)

        # qtawesome (optional)
        self._qta = _try_qtawesome()

        self._setup_menu()
        self._setup_ui()

        # Apply config defaults to panels
        self._apply_config()

    def _apply_runtime_settings(self) -> None:
        """Push settings that affect processing into the running app."""
        from core.ffmpeg import set_ffmpeg_path, set_threads
        from core.nvenc import set_nvenc_enabled
        from core.vram_manager import vram_manager

        # A cleared FFmpeg override falls back to the binary detected at startup
        if self.config.ffmpeg.path and self.config.ffmpeg.path != "ffmpeg":
            set_ffmpeg_path(self.config.ffmpeg.path)
        else:
            set_ffmpeg_path(self.ffmpeg_path)
        set_threads(self.config.ffmpeg.threads)
        set_nvenc_enabled(self.config.gpu.use_nvenc)
        vram_manager.apply_device_preference(self.config.gpu.device)
        # Concurrency applies to the live queue, not just after a restart
        self.queue.concurrent_jobs = self.config.general.concurrent_jobs

    def _apply_config(self) -> None:
        """Apply saved config to UI panels."""
        self._apply_runtime_settings()
        self.tools_panel.apply_config(self.config)
        if self.config.general.default_output_dir:
            out_dir = Path(self.config.general.default_output_dir)
            if out_dir.exists():
                self.output_panel.set_output_dir(out_dir)

    def _make_action(self, text: str, shortcut: str = "", icon_name: str = "", icon_color: str = "#e85d04") -> QAction:
        """Create a QAction with optional icon (qtawesome if available)."""
        icon = _icon(self._qta, icon_name, icon_color) if icon_name else None
        if icon:
            return QAction(icon, text, self, shortcut=shortcut)
        return QAction(text, self, shortcut=shortcut)

    def _setup_menu(self) -> None:
        """Build the menu bar with icons."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        self.action_open = self._make_action("&Open File...", "Ctrl+O", "mdi.folder-open")
        self.action_open.triggered.connect(self._on_open_file)
        file_menu.addAction(self.action_open)

        action_open_folder = self._make_action("Open &Folder...", icon_name="mdi.folder-multiple")
        action_open_folder.triggered.connect(self._on_open_folder)
        file_menu.addAction(action_open_folder)
        file_menu.addSeparator()

        action_exit = self._make_action("E&xit", "Ctrl+Q", "mdi.exit-to-app", "#888")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        self.action_settings = self._make_action("&Settings...", "Ctrl+,", "mdi.cog")
        self.action_settings.triggered.connect(self._on_settings)
        tools_menu.addAction(self.action_settings)

        self.action_models = self._make_action("&Model Manager...", icon_name="mdi.package-variant")
        self.action_models.triggered.connect(self._on_model_manager)
        tools_menu.addAction(self.action_models)

        # Queue menu
        queue_menu = menubar.addMenu("&Queue")
        self.action_start = self._make_action("&Start Queue", "F5", "mdi.play-circle", "#4ec9b0")
        self.action_start.triggered.connect(self._on_start_queue)
        queue_menu.addAction(self.action_start)

        action_pause = self._make_action("&Pause", "F6", "mdi.pause-circle", "#e8a000")
        action_pause.triggered.connect(self._on_pause_queue)
        queue_menu.addAction(action_pause)

        action_cancel = self._make_action("C&ancel", "Shift+F5", "mdi.stop-circle", "#f44747")
        action_cancel.triggered.connect(self._on_cancel_selected)
        queue_menu.addAction(action_cancel)
        queue_menu.addSeparator()

        self.action_clear = self._make_action("C&lear Completed")
        self.action_clear.triggered.connect(self._on_clear_completed)
        queue_menu.addAction(self.action_clear)

        # View menu
        view_menu = menubar.addMenu("&View")
        self.action_clear_log = self._make_action("&Clear Log", "Ctrl+L", "mdi.delete-sweep", "#888")
        self.action_clear_log.triggered.connect(self._on_clear_log)
        view_menu.addAction(self.action_clear_log)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self._make_action("&About VideoCraft"))

    def _setup_ui(self) -> None:
        """Build the main splitter layout with panels."""
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(splitter)

        # Top section: source | output (horizontal)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Source panel
        self.source_panel = SourcePanel()
        top_splitter.addWidget(self.source_panel)

        # Output panel
        self.output_panel = OutputPanel()
        top_splitter.addWidget(self.output_panel)

        splitter.addWidget(top_splitter)

        # Tools panel — guaranteed a usable minimum height; it scrolls
        # internally beyond that so controls are never clipped.
        self.tools_panel = ToolsPanel()
        self.tools_panel.setMinimumHeight(180)
        splitter.addWidget(self.tools_panel)

        # Queue panel
        self.queue_panel = QueuePanel(self.queue)
        self.queue_panel.add_requested.connect(self._on_add_selected_to_queue)
        self.queue_panel.start_requested.connect(self._on_start_queue)
        self.queue_panel.pause_requested.connect(self._on_pause_queue)
        self.queue_panel.cancel_requested.connect(self._on_cancel_selected)
        splitter.addWidget(self.queue_panel)

        # Log panel
        self.log_panel = LogPanel()
        splitter.addWidget(self.log_panel)

        # Set initial splitter sizes. The tools panel scrolls internally,
        # so give it enough height up front to show a tool's controls
        # without scrolling; users can still drag the handles.
        splitter.setStretchFactor(0, 2)  # top section
        splitter.setStretchFactor(1, 2)  # tools
        splitter.setStretchFactor(2, 1)  # queue
        splitter.setStretchFactor(3, 1)  # log
        splitter.setSizes([300, 320, 190, 150])

    # ── Drag-and-drop on main window ──

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events with valid files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(Path(u.toLocalFile()).suffix.lower() in _ALL_EXTS for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle dropped files — add them to the queue."""
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in _ALL_EXTS and path.exists():
                self._add_to_queue(path)

    # ── File actions ──

    def _on_open_file(self) -> None:
        """Open file dialog and add selected files to queue."""
        filters = (
            "Media Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v *.mpg *.mpeg"
            " *.mp3 *.aac *.flac *.wav *.ogg *.m4a);;"
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v);;"
            "Audio Files (*.mp3 *.aac *.flac *.wav *.ogg *.m4a)"
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Media File(s)", "", filters
        )
        for f in files:
            self._add_to_queue(Path(f))

    def _on_open_folder(self) -> None:
        """Open folder and add all video files."""
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        p = Path(folder)
        for f in sorted(p.iterdir()):
            if f.suffix.lower() in _ALL_EXTS:
                self._add_to_queue(f)

    def _add_to_queue(self, source_path: Path) -> None:
        """Create a job for the active tool tab and add it to the queue."""
        tool = self.tools_panel.current_tool()

        params = self.tools_panel.get_params(tool)

        output_dir = self.output_panel.output_dir()
        if output_dir is None:
            output_dir = source_path.parent

        ext = self._output_extension(tool, params, source_path)
        output_path = output_dir / f"{source_path.stem}_output{ext}"

        job = Job(
            source_path=source_path,
            output_path=output_path,
            pipeline=[tool],
            params=params,
        )
        self.queue.add(job)
        self.queue_panel.add_job(job)
        self.append_log(f"[INFO] Added to queue: {source_path.name} ({tool})")

    @staticmethod
    def _output_extension(tool: str, params: dict, source_path: Path) -> str:
        """Pick the output file extension for a tool's actual output format."""
        if tool == "converter":
            return "." + params.get("container", "mp4")
        if tool in ("upscaler", "denoiser", "colorizer"):
            return ".mp4"  # frame pipeline re-encodes to H.264 + AAC
        if tool == "hdr":
            return ".mkv"  # HEVC + copied source audio — MKV takes anything
        if tool == "vocal_remover" and source_path.suffix.lower() in _AUDIO_EXTS:
            return "." + params.get("output_format", "wav")
        return source_path.suffix  # vocal remover remux / upmixer keep container

    def _on_add_selected_to_queue(self) -> None:
        """Queue the files selected in the Source panel with the active tool."""
        files = self.source_panel.selected_files()
        if not files:
            self.append_log("[WARNING] No files selected — open files in the Source panel first")
            return
        for f in files:
            self._add_to_queue(f)
        self.source_panel.clear_selection()

    # ── Tools actions ──

    def _on_settings(self) -> None:
        """Open the settings dialog."""
        old_theme = self.config.general.theme
        dialog = SettingsDialog(self.config, self)
        # The dialog saves the config itself on Accept — no second save here.
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.append_log("[INFO] Settings saved")

            self._apply_runtime_settings()
            self.tools_panel.apply_config(self.config)

            # Runtime theme switching (compare against the pre-dialog theme;
            # the dialog has already written the new one into self.config)
            new_theme = dialog.get_theme()
            if new_theme != old_theme:
                self._apply_theme(new_theme)

    def _apply_theme(self, theme: str) -> None:
        """Apply a qt-material theme at runtime.

        apply_theme also re-applies the custom QSS recolored to the new
        theme's accent, so the whole UI re-tints to match the selection.
        """
        from core.theme import apply_theme
        try:
            app = QApplication.instance()
            applied = apply_theme(app, theme)
            self.append_log(f"[INFO] Theme changed to: {applied}")
        except Exception as e:
            self.append_log(f"[WARNING] Could not apply theme: {e}")

    def _on_model_manager(self) -> None:
        """Open the model manager dialog."""
        dialog = ModelManagerDialog(self)
        dialog.exec()

    # ── Queue actions ──

    def _on_start_queue(self) -> None:
        """Start (or resume) processing the queue."""
        if self._queue_active:
            return  # already dispatching

        # Pre-flight every distinct queued ML setup (pipeline + output disk),
        # not just the first job — later jobs may need other models or disks.
        seen: set[tuple] = set()
        for job in list(self.queue.jobs):
            if job.status != "queued" or not is_ml_job(job):
                continue
            key = (tuple(job.pipeline), job.output_path.parent)
            if key in seen:
                continue
            seen.add(key)

            from ui.dialogs.preflight_dialog import PreflightDialog

            dialog = PreflightDialog(job, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.append_log("[INFO] Queue start cancelled at pre-flight check")
                return

        self._queue_active = True
        self.queue_panel.start_timer()
        self._dispatch()

    def _on_pause_queue(self) -> None:
        """Pause dispatching — running jobs finish, no new jobs start."""
        if not self._queue_active:
            return
        self._queue_active = False
        if self._workers:
            self.append_log("[INFO] Queue paused — running jobs will finish, no new jobs will start")
        else:
            self.append_log("[INFO] Queue paused")
            self.queue_panel.stop_timer()

    def _on_cancel_selected(self) -> None:
        """Cancel the job(s) selected in the queue table."""
        job_ids = self.queue_panel.selected_job_ids()
        if not job_ids:
            self.append_log("[WARNING] No jobs selected — select rows in the queue to cancel")
            return
        names = {j.id: j.source_path.name for j in self.queue.jobs}
        for job_id in job_ids:
            self.queue.cancel(job_id)
            self.append_log(f"[INFO] Cancel requested: {names.get(job_id, job_id)}")

    def _on_clear_completed(self) -> None:
        """Clear completed jobs from the queue."""
        self.queue_panel.clear_completed()
        self.append_log("[INFO] Cleared completed jobs")

    def _on_clear_log(self) -> None:
        """Clear the log panel."""
        self.log_panel.clear_log()

    def _dispatch(self) -> None:
        """Start as many queued jobs as concurrency limits allow.

        Driven by _on_start_queue and by workers finishing — no polling.
        """
        if not self._queue_active:
            return

        while True:
            job = self.queue.next_startable()
            if job is None:
                break
            self._start_worker(job)

        if not self._workers and self.queue.next_available() is None:
            # Nothing queued and nothing running → queue is finished
            self._queue_active = False
            self.queue_panel.stop_timer()
            self.append_log("[INFO] Queue finished")

    def _start_worker(self, job: Job) -> None:
        """Spin up a worker thread for a job."""
        # Mark running here (GUI thread) so a re-entrant _dispatch cannot
        # pick the same job again before the thread gets scheduled.
        job.status = "running"

        worker = Worker(job)
        worker.log_line.connect(self.append_log)
        worker.job_done.connect(self._on_job_done)
        worker.job_failed.connect(self._on_job_failed)
        worker.started.connect(lambda: self.append_log(f"[INFO] Started: {job.source_path.name}"))
        # Drop our reference only once the thread has actually finished —
        # popping in job_done/job_failed can destroy the QThread while its
        # run() is still unwinding.
        worker.finished.connect(lambda job_id=job.id: self._on_worker_finished(job_id))

        self._workers[job.id] = worker
        self.queue.mark_active(job.id)
        worker.start()

    def _on_worker_finished(self, job_id: str) -> None:
        """A worker thread finished — release it and dispatch the next job."""
        self._workers.pop(job_id, None)
        self.queue.mark_finished(job_id)
        if self._queue_active:
            self._dispatch()
        elif not self._workers:
            # Paused and the last running job just drained
            self.queue_panel.stop_timer()

    def _on_job_done(self, job: Job) -> None:
        """Handle job completion."""
        self.append_log(f"[SUCCESS] Done: {job.source_path.name} → {job.output_path.name}")

    def _on_job_failed(self, job: Job, error: str) -> None:
        """Handle job failure."""
        self.append_log(f"[ERROR] Failed: {job.source_path.name} — {error}")

    def append_log(self, line: str) -> None:
        """Convenience method to append to log panel."""
        self.log_panel.append_log(line)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel running jobs and wait for worker threads before closing."""
        workers = list(self._workers.values())
        if workers:
            self.append_log("[INFO] Shutting down — cancelling running jobs...")
            for worker in workers:
                worker.job.cancelled = True
            for worker in workers:
                if not worker.wait(15000):
                    logger.warning("Worker for job %s did not stop in time", worker.job.id)
        event.accept()
