"""Tests for Phase 1 UI panels — source, output, queue."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from pathlib import Path
from videocraft.core.job import Job
from videocraft.core.job_queue import JobQueue
from videocraft.ui.panels.source_panel import SourcePanel
from videocraft.ui.panels.output_panel import OutputPanel
from videocraft.ui.panels.tools_panel import ToolsPanel
from videocraft.ui.panels.queue_panel import QueuePanel


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


def test_output_panel_set_dir():
    """Output dir can be set programmatically."""
    panel = OutputPanel()
    panel.set_output_dir(Path("/tmp/output"))
    assert panel.output_dir() == Path("/tmp/output")
    assert "/tmp/output" in panel.lbl_destination.text()


def test_convert_tab_defaults():
    """Convert tab has sensible defaults."""
    panel = ToolsPanel()
    params = panel.get_params("converter")
    assert params["container"] == "mp4"
    assert params["video_codec"] == "h264"
    assert params["audio_codec"] == "aac"
    assert params["crf"] == 23


def test_convert_tab_crf_slider():
    """CRF slider updates params and label; manual change clears the preset."""
    panel = ToolsPanel()
    panel.convert_crf.setValue(20)
    assert panel.get_params("converter")["crf"] == 20
    assert panel.convert_crf_label.text() == "20"
    assert not any(b.isChecked() for b in panel._crf_presets.values())


def test_convert_tab_preset():
    """Preset buttons set CRF and stay checked."""
    panel = ToolsPanel()
    panel._crf_presets["Fast"].click()
    assert panel.get_params("converter")["crf"] == 28
    assert panel._crf_presets["Fast"].isChecked()
    panel._crf_presets["Quality"].click()
    assert panel.get_params("converter")["crf"] == 18


def test_convert_tab_format_selection():
    """Format/codec selection maps to correct params."""
    panel = ToolsPanel()
    panel.convert_container.setCurrentText("MKV")
    panel.convert_video_codec.setCurrentText("H.265")
    panel.convert_audio_codec.setCurrentText("None")
    params = panel.get_params("converter")
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
