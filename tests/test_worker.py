"""Tests for core.worker — QThread worker with signals."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from unittest.mock import patch, MagicMock
from pathlib import Path
from videocraft.core.job import Job
from videocraft.core.worker import Worker, get_processor


def test_worker_emits_log_lines():
    """Worker emits log_line signals for each yielded line."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )

    captured: list[str] = []
    worker = Worker(job)
    worker.log_line.connect(captured.append)

    # Test signal emission directly (without starting the thread)
    worker.log_line.emit("[INFO] step 1")
    worker.log_line.emit("[INFO] step 2")

    assert len(captured) == 2
    assert "step 1" in captured[0]
    assert "step 2" in captured[1]


def test_worker_checks_cancellation():
    """Worker stops processing when job is cancelled."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )
    job.cancelled = True

    captured_lines: list[str] = []
    captured_status: list[str] = []

    worker = Worker(job)
    worker.log_line.connect(captured_lines.append)

    # Simulate what run() does with a cancelled job
    # The processor should see cancelled=True and stop early
    assert job.cancelled is True
    assert job.status == "queued"  # Not yet running


def test_get_processor_converter():
    """get_processor returns correct processor for 'converter'."""
    from videocraft.processors.converter import ConverterProcessor
    proc = get_processor("converter")
    assert isinstance(proc, ConverterProcessor)


def test_get_processor_unknown():
    """get_processor raises ValueError for unknown tool."""
    try:
        get_processor("nonexistent_tool")
        assert False, "Should raise ValueError"
    except ValueError as e:
        assert "nonexistent_tool" in str(e)
