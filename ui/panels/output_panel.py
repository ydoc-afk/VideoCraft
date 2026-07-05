"""Output panel — destination folder, format/codec selector, quality settings."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QComboBox,
    QSlider,
    QGroupBox,
    QButtonGroup,
)
from PyQt6.QtCore import Qt


class OutputPanel(QFrame):
    """Output panel — destination, format, codec, quality settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Destination folder
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination:"))
        self.lbl_destination = QLabel("Select output folder...")
        self.lbl_destination.setStyleSheet("color: #888;")
        dest_layout.addWidget(self.lbl_destination, 1)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_folder)
        dest_layout.addWidget(self.btn_browse)
        layout.addLayout(dest_layout)

        # Format selection
        fmt_group = QGroupBox("Format")
        fmt_layout = QHBoxLayout()

        fmt_layout.addWidget(QLabel("Container:"))
        self.cmb_container = QComboBox()
        self.cmb_container.addItems(["MP4", "MKV", "MOV", "AVI", "WebM", "GIF"])
        fmt_layout.addWidget(self.cmb_container)

        fmt_layout.addWidget(QLabel("Video Codec:"))
        self.cmb_video_codec = QComboBox()
        self.cmb_video_codec.addItems(["H.264", "H.265", "AV1", "VP9", "Copy"])
        fmt_layout.addWidget(self.cmb_video_codec)

        fmt_layout.addWidget(QLabel("Audio Codec:"))
        self.cmb_audio_codec = QComboBox()
        self.cmb_audio_codec.addItems(["AAC", "MP3", "FLAC", "Copy", "None"])
        fmt_layout.addWidget(self.cmb_audio_codec)

        fmt_group.setLayout(fmt_layout)
        layout.addWidget(fmt_group)

        # Quality
        qual_group = QGroupBox("Quality")
        qual_layout = QVBoxLayout()

        crf_layout = QHBoxLayout()
        crf_layout.addWidget(QLabel("CRF:"))
        self.scr_crf = QSlider(Qt.Orientation.Horizontal)
        self.scr_crf.setRange(0, 51)
        self.scr_crf.setValue(23)
        self.scr_crf.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.scr_crf.setTickInterval(1)
        crf_layout.addWidget(self.scr_crf)
        self.lbl_crf = QLabel("23")
        self.lbl_crf.setFixedWidth(30)
        crf_layout.addWidget(self.lbl_crf)
        self.scr_crf.valueChanged.connect(self._on_crf_changed)
        qual_layout.addLayout(crf_layout)

        # Preset buttons (mutually exclusive via QButtonGroup)
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)

        self.btn_fast = QPushButton("Fast")
        self.btn_fast.setCheckable(True)
        self.btn_fast.clicked.connect(lambda: self._set_crf_preset(28))
        self._preset_group.addButton(self.btn_fast)
        preset_layout.addWidget(self.btn_fast)

        self.btn_balanced = QPushButton("Balanced")
        self.btn_balanced.setCheckable(True)
        self.btn_balanced.setChecked(True)
        self.btn_balanced.clicked.connect(lambda: self._set_crf_preset(23))
        self._preset_group.addButton(self.btn_balanced)
        preset_layout.addWidget(self.btn_balanced)

        self.btn_quality = QPushButton("Quality")
        self.btn_quality.setCheckable(True)
        self.btn_quality.clicked.connect(lambda: self._set_crf_preset(18))
        self._preset_group.addButton(self.btn_quality)
        preset_layout.addWidget(self.btn_quality)

        qual_layout.addLayout(preset_layout)
        qual_group.setLayout(qual_layout)
        layout.addWidget(qual_group)

        layout.addStretch()

        # Store selected output dir
        self._output_dir: Path | None = None

    def _browse_folder(self) -> None:
        """Open folder picker for output directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._output_dir = Path(folder)
            self.lbl_destination.setText(folder)
            self.lbl_destination.setStyleSheet("")

    def _on_crf_changed(self, value: int) -> None:
        """Update CRF label when slider changes."""
        self.lbl_crf.setText(str(value))
        # Uncheck preset buttons on *manual* adjustment only — preset clicks
        # also move the slider and must not uncheck themselves.
        if getattr(self, "_applying_preset", False):
            return
        # An exclusive QButtonGroup ignores programmatic unchecks, so lift
        # exclusivity for a moment to reach the "no preset" state.
        self._preset_group.setExclusive(False)
        self.btn_fast.setChecked(False)
        self.btn_balanced.setChecked(False)
        self.btn_quality.setChecked(False)
        self._preset_group.setExclusive(True)

    def _set_crf_preset(self, crf: int) -> None:
        """Set CRF from preset button."""
        self._applying_preset = True
        try:
            self.scr_crf.setValue(crf)
            self.lbl_crf.setText(str(crf))
        finally:
            self._applying_preset = False

    def get_params(self) -> dict:
        """Return current settings as a params dict for the job."""
        container_map = {
            "MP4": "mp4", "MKV": "mkv", "MOV": "mov",
            "AVI": "avi", "WebM": "webm", "GIF": "gif",
        }
        video_map = {
            "H.264": "h264", "H.265": "h265", "AV1": "av1",
            "VP9": "vp9", "Copy": "copy",
        }
        audio_map = {
            "AAC": "aac", "MP3": "mp3", "FLAC": "flac",
            "Copy": "copy", "None": "none",
        }

        return {
            "container": container_map.get(self.cmb_container.currentText(), "mp4"),
            "video_codec": video_map.get(self.cmb_video_codec.currentText(), "h264"),
            "audio_codec": audio_map.get(self.cmb_audio_codec.currentText(), "aac"),
            "crf": self.scr_crf.value(),
        }

    def output_dir(self) -> Path | None:
        """Return the selected output directory."""
        return self._output_dir

    def set_output_dir(self, path: Path) -> None:
        """Set the output directory programmatically."""
        self._output_dir = path
        self.lbl_destination.setText(str(path))
        self.lbl_destination.setStyleSheet("")
