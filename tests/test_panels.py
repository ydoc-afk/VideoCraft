"""Tests for Phase 1 UI panels — source, output, queue."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from pathlib import Path
from core.job import Job
from core.job_queue import JobQueue
from ui.panels.source_panel import SourcePanel
from ui.panels.output_panel import OutputPanel
from ui.panels.queue_panel import QueuePanel


def test_source_panel_creates():
    """Source panel creates without crashing."""
    panel = SourcePanel()
    assert panel.selected_files() == []


def test_source_panel_accepts_video_exts():
    """Source panel tracks video files by extension."""
    panel = SourcePanel()
    # Simulate adding files
    panel._selected_files = [Path("/tmp/video.mp4"), Path("/tmp/clip.mkv")]
    panel._update_display()
    assert len(panel.selected_files()) == 2
    assert "2 file(s)" in panel.label_files.text()


def test_output_panel_defaults():
    """Output panel has sensible defaults."""
    panel = OutputPanel()
    params = panel.get_params()
    assert params["container"] == "mp4"
    assert params["video_codec"] == "h264"
    assert params["audio_codec"] == "aac"
    assert params["crf"] == 23


def test_output_panel_crf_slider():
    """CRF slider updates params."""
    panel = OutputPanel()
    panel.scr_crf.setValue(18)
    panel._on_crf_changed(18)
    assert panel.get_params()["crf"] == 18
    assert panel.lbl_crf.text() == "18"


def test_output_panel_preset():
    """Preset buttons set CRF correctly."""
    panel = OutputPanel()
    panel._set_crf_preset(28)  # Fast
    assert panel.get_params()["crf"] == 28
    panel._set_crf_preset(18)  # Quality
    assert panel.get_params()["crf"] == 18


def test_output_panel_set_dir():
    """Output dir can be set programmatically."""
    panel = OutputPanel()
    panel.set_output_dir(Path("/tmp/output"))
    assert panel.output_dir() == Path("/tmp/output")
    assert "/tmp/output" in panel.lbl_destination.text()


def test_output_panel_format_selection():
    """Format/codec selection maps to correct params."""
    panel = OutputPanel()
    panel.cmb_container.setCurrentText("MKV")
    panel.cmb_video_codec.setCurrentText("H.265")
    panel.cmb_audio_codec.setCurrentText("None")
    params = panel.get_params()
    assert params["container"] == "mkv"
    assert params["video_codec"] == "h265"
    assert params["audio_codec"] == "none"


def test_queue_panel_creates():
    """Queue panel creates with job queue."""
    q = JobQueue()
    panel = QueuePanel(q)
    assert panel.table.rowCount() == 0


def test_queue_panel_add_job():
    """Adding a job to queue panel shows it in the table."""
    q = JobQueue()
    panel = QueuePanel(q)
    job = Job(
        source_path=Path("/tmp/test.mp4"),
        output_path=Path("/tmp/test_out.mp4"),
        pipeline=["converter"],
    )
    q.add(job)
    panel.add_job(job)

    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "test.mp4"
    assert panel.table.item(0, 1).text() == "converter"


def test_queue_panel_clear_completed():
    """Clear completed removes done jobs from table."""
    q = JobQueue()
    panel = QueuePanel(q)

    j1 = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a.mp4"), pipeline=["converter"])
    j2 = Job(source_path=Path("/tmp/b.mp4"), output_path=Path("/tmp/b.mp4"), pipeline=["converter"])
    j1.status = "done"
    q.add(j1)
    q.add(j2)
    panel.add_job(j1)
    panel.add_job(j2)

    panel._on_clear()

    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "b.mp4"
