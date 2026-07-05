"""Tests for main.py and ui.main_window — app shell with Phase 1 wiring."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from pathlib import Path
from unittest.mock import patch, MagicMock
from core.job import Job


def test_main_window_launches():
    """Main window creates without crashing."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    assert win.windowTitle() == "VideoCraft — AI Video Enhancement"
    assert win.minimumWidth() >= 1100
    assert win.minimumHeight() >= 700


def test_main_window_has_all_panels():
    """Main window has source, output, queue, and log panels."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    assert win.source_panel is not None
    assert win.output_panel is not None
    assert win.queue_panel is not None
    assert win.log_panel is not None


def test_main_window_has_menu_bar():
    """Main window has menu bar with expected menus."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    menus = [m.text() for m in win.menuBar().actions()]
    assert "&File" in menus
    assert "&Tools" in menus
    assert "&Queue" in menus
    assert "&View" in menus
    assert "&Help" in menus


def test_main_window_add_to_queue():
    """Adding a file to queue creates a job for the active tool tab."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    win.output_panel.set_output_dir(Path("/tmp/output"))

    # Convert tab active → converter job with Output panel params
    win.tools_panel.tab_widget.setCurrentIndex(5)
    win._add_to_queue(Path("/tmp/test.mp4"))

    assert len(win.queue.jobs) == 1
    job = win.queue.jobs[0]
    assert job.source_path == Path("/tmp/test.mp4")
    assert job.output_path.parent == Path("/tmp/output")
    assert job.pipeline == ["converter"]
    assert "container" in job.params


def test_main_window_add_to_queue_uses_active_tool():
    """The active tools tab decides the pipeline and output extension."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    win.output_panel.set_output_dir(Path("/tmp/output"))

    # Upscaler tab (index 0) → upscaler job, .mp4 output (frame pipeline)
    win.tools_panel.tab_widget.setCurrentIndex(0)
    win._add_to_queue(Path("/tmp/test.webm"))

    job = win.queue.jobs[0]
    assert job.pipeline == ["upscaler"]
    assert job.output_path.suffix == ".mp4"
    assert "scale" in job.params

    # Colorizer tab → backend/style split the processor understands
    win.tools_panel.tab_widget.setCurrentIndex(2)
    win._add_to_queue(Path("/tmp/test2.mp4"))
    job2 = win.queue.jobs[1]
    assert job2.pipeline == ["colorizer"]
    assert job2.params["backend"] in ("ddcolor", "deoldify")
    assert job2.params["style"] in ("artistic", "stable", "video")


def test_main_window_log():
    """Log panel receives log lines."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    win.append_log("[INFO] Test message")
    assert "Test message" in win.log_panel.log_edit.toPlainText()


def test_main_window_clear_log():
    """Clear log action works."""
    from ui.main_window import MainWindow
    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    win.append_log("[INFO] Before clear")
    win._on_clear_log()
    assert win.log_panel.log_edit.toPlainText() == ""


def test_find_ffmpeg_bundled(tmp_path):
    """Bundled FFmpeg is found before PATH.

    Uses a temp project root — must NOT touch the real assets/bin, which
    may hold an actually-bundled static ffmpeg.
    """
    import main
    bin_dir = tmp_path / "assets" / "bin"
    bin_dir.mkdir(parents=True)
    fake = bin_dir / "ffmpeg"
    fake.touch()
    with patch.object(main, "project_root", tmp_path):
        assert main.find_ffmpeg() == fake


def test_find_ffmpeg_none(tmp_path):
    """Returns None when FFmpeg is not found anywhere (empty temp root)."""
    import main
    with patch.object(main, "project_root", tmp_path), \
         patch("main.shutil.which", return_value=None):
        assert main.find_ffmpeg() is None
