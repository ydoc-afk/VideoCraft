"""VideoCraft — Entry point."""

import sys
import shutil
import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout

# Ensure project root is on sys.path for bundled execution
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def find_ffmpeg() -> Path | None:
    """Find FFmpeg binary: bundled first, then PATH fallback."""
    # When frozen by PyInstaller, bundled data lives under sys._MEIPASS.
    base = Path(getattr(sys, "_MEIPASS", project_root))
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    bundled = base / "assets" / "bin" / name
    if bundled.exists():
        logger.info("Found bundled FFmpeg: %s", bundled)
        return bundled

    # Check PATH
    found = shutil.which("ffmpeg")
    if found:
        logger.info("Found FFmpeg on PATH: %s", found)
        return Path(found)

    return None


def show_ffmpeg_error(parent=None) -> None:
    """Show error dialog when FFmpeg is not found."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("FFmpeg Not Found")
    layout = QVBoxLayout(dialog)

    label = QLabel(
        "FFmpeg is required but was not found.\n\n"
        "Please install FFmpeg and ensure it is on your PATH, or\n"
        "place ffmpeg (or ffmpeg.exe) in assets/bin/.\n\n"
        "https://ffmpeg.org/download.html"
    )
    label.setWordWrap(True)
    layout.addWidget(label)

    btn = QPushButton("Exit")
    btn.clicked.connect(dialog.reject)
    layout.addWidget(btn)

    dialog.exec()


def main() -> int:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("VideoCraft")
    app.setApplicationVersion("0.1.0")

    # Apply qt-material theme BEFORE showing any windows. apply_theme
    # validates the name against what qt-material ships and also applies the
    # custom QSS overrides (recolored to the theme's accent).
    from core.config import AppConfig
    from core.theme import apply_theme
    _cfg = AppConfig.load(AppConfig.platform_config_path())
    apply_theme(app, _cfg.general.theme)

    # Check FFmpeg
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        logger.error("FFmpeg not found")
        show_ffmpeg_error()
        return 1

    # Make the found binary the one every processor uses
    from core.ffmpeg import set_ffmpeg_path
    set_ffmpeg_path(ffmpeg_path)

    # Honor the NVENC preference before any encode job can run
    from core.nvenc import set_nvenc_enabled
    set_nvenc_enabled(_cfg.gpu.use_nvenc)

    # Import and show main window (after theme + FFmpeg check)
    from ui.main_window import MainWindow
    window = MainWindow(ffmpeg_path=ffmpeg_path)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
