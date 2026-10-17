"""Output panel — destination folder."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
)

from core.theme import mark_hint


class OutputPanel(QFrame):
    """Output panel — where finished files are written.

    Converter format/codec/quality settings live on the Convert tab of the
    ToolsPanel, alongside every other tool's settings."""

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
        mark_hint(self.lbl_destination, True)
        dest_layout.addWidget(self.lbl_destination, 1)
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_folder)
        dest_layout.addWidget(self.btn_browse)
        layout.addLayout(dest_layout)

        layout.addStretch()

        # Store selected output dir
        self._output_dir: Path | None = None

    def _browse_folder(self) -> None:
        """Open folder picker for output directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._output_dir = Path(folder)
            self.lbl_destination.setText(folder)
            mark_hint(self.lbl_destination, False)

    def output_dir(self) -> Path | None:
        """Return the selected output directory."""
        return self._output_dir

    def set_output_dir(self, path: Path) -> None:
        """Set the output directory programmatically."""
        self._output_dir = path
        self.lbl_destination.setText(str(path))
        mark_hint(self.lbl_destination, False)
