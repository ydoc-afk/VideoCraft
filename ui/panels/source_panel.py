"""Source panel — file picker with drag-and-drop, ffprobe metadata, thumbnail."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
)
from PyQt6.QtCore import Qt, QMimeData

from core.theme import mark_hint
from PyQt6.QtGui import QPixmap, QPainter

from ui.widgets.drag_drop_area import DragDropArea

logger = logging.getLogger(__name__)

# Accepted extensions (video + audio — audio tools accept audio-only sources)
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"}
_AUDIO_EXTS = {".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"}
_MEDIA_EXTS = _VIDEO_EXTS | _AUDIO_EXTS


class SourcePanel(QFrame):
    """Source panel — file picker, metadata display, thumbnail preview."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAcceptDrops(True)
        self._selected_files: list[Path] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Button row
        btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open File(s)")
        self.btn_open.clicked.connect(self._open_files)
        btn_layout.addWidget(self.btn_open)

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.btn_open_folder)
        layout.addLayout(btn_layout)

        # Visible drop target (the whole panel accepts drops too). Capped so
        # it doesn't dominate the panel's height and crowd the panels below.
        self.drop_area = DragDropArea("Drop video or audio files here")
        self.drop_area.files_dropped.connect(self._on_files_dropped)
        self.drop_area.setMaximumHeight(84)
        layout.addWidget(self.drop_area)

        # Thumbnail + metadata split
        mid_layout = QHBoxLayout()

        # Thumbnail area
        self.thumbnail_scene = QGraphicsScene()
        self.thumbnail_view = QGraphicsView(self.thumbnail_scene)
        self.thumbnail_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.thumbnail_view.setMaximumWidth(320)
        self.thumbnail_view.setMinimumHeight(120)
        mid_layout.addWidget(self.thumbnail_view, 1)

        # Metadata table
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.metadata_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        mid_layout.addWidget(self.metadata_table, 1)

        layout.addLayout(mid_layout)

        # Selected files label
        self.label_files = QLabel("No files selected")
        self.label_files.setStyleSheet("padding: 8px;")
        mark_hint(self.label_files, True)
        layout.addWidget(self.label_files)

    def _open_files(self) -> None:
        """Open file dialog for media files."""
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
            p = Path(f)
            if p.suffix.lower() in _MEDIA_EXTS and p not in self._selected_files:
                self._selected_files.append(p)
        self._update_display()

    def _open_folder(self) -> None:
        """Open folder and add all video files."""
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        for p in sorted(Path(folder).iterdir()):
            if p.suffix.lower() in _MEDIA_EXTS and p not in self._selected_files:
                self._selected_files.append(p)
        self._update_display()

    def _update_display(self) -> None:
        """Update file count label and show first file's metadata."""
        count = len(self._selected_files)
        self.label_files.setText(f"{count} file(s) selected")

        if self._selected_files:
            self._show_metadata(self._selected_files[0])

    def _show_metadata(self, path: Path) -> None:
        """Show video metadata via ffprobe."""
        info = self._probe_metadata(path)
        self.metadata_table.setRowCount(len(info))
        for i, (key, value) in enumerate(info.items()):
            self.metadata_table.setItem(i, 0, QTableWidgetItem(key))
            self.metadata_table.setItem(i, 1, QTableWidgetItem(str(value)))

        # Extract thumbnail
        self._extract_thumbnail(path)

    @staticmethod
    def _probe_metadata(path: Path) -> dict[str, str]:
        """Get video metadata via ffprobe."""
        info: dict[str, str] = {"File": path.name, "Path": str(path)}
        try:
            from core.ffmpeg import ffprobe_cmd
            cmd = [
                ffprobe_cmd(), "-v", "error",
                "-show_entries", "stream=width,height,duration,r_frame_rate,codec_name,bit_rate",
                "-show_entries", "format=duration,size",
                "-of", "default=noprint_wrappers=1",
                str(path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        info[k.strip()] = v.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning("ffprobe failed: %s", e)
            info["Error"] = str(e)
        return info

    def _extract_thumbnail(self, path: Path) -> None:
        """Extract a thumbnail frame from the video."""
        self.thumbnail_scene.clear()
        try:
            from core.ffmpeg import ffmpeg_cmd
            cmd = [
                ffmpeg_cmd(), "-y", "-i", str(path),
                "-vframes", "1", "-vf", "thumbnail=50,scale=320:-1",
                "-f", "image2pipe", "-vcodec", "mjpeg", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                pixmap = QPixmap()
                pixmap.loadFromData(result.stdout)
                if not pixmap.isNull():
                    self.thumbnail_scene.addPixmap(pixmap.scaled(
                        320, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # Thumbnail is optional

    def dragEnterEvent(self, event) -> None:
        """Accept drag events with video files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(Path(u.toLocalFile()).suffix.lower() in _MEDIA_EXTS for u in urls):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """Handle dropped video files."""
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in _MEDIA_EXTS and p not in self._selected_files:
                self._selected_files.append(p)
        self._update_display()

    def _on_files_dropped(self, files: list[Path]) -> None:
        """Handle files dropped on the DragDropArea widget."""
        for p in files:
            if p not in self._selected_files:
                self._selected_files.append(p)
        self._update_display()

    def selected_files(self) -> list[Path]:
        """Return list of selected file paths."""
        return list(self._selected_files)

    def clear_selection(self) -> None:
        """Clear the selected files list (e.g., after queueing them)."""
        self._selected_files.clear()
        self.label_files.setText("No files selected")
