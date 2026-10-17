"""Tests for core.process.run_cancellable and cancellation of long steps."""

import stat
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from videocraft.core.job import Job
from videocraft.core.process import Cancelled, run_cancellable
import subprocess


def test_returns_output_like_subprocess_run():
    r = run_cancellable([sys.executable, "-c", "print('hi')"], lambda: False, 10)
    assert r.returncode == 0 and r.stdout.strip() == "hi"


def test_nonzero_exit_is_returned_not_raised():
    r = run_cancellable([sys.executable, "-c", "import sys; sys.exit(3)"], lambda: False, 10)
    assert r.returncode == 3


def test_cancel_terminates_child_quickly():
    flag = {"c": False}
    threading.Timer(0.4, lambda: flag.update(c=True)).start()
    t = time.monotonic()
    with pytest.raises(Cancelled):
        run_cancellable([sys.executable, "-c", "import time; time.sleep(30)"], lambda: flag["c"], 60)
    assert time.monotonic() - t < 5


def test_timeout_kills_child():
    t = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_cancellable([sys.executable, "-c", "import time; time.sleep(30)"], lambda: False, 0.5)
    assert time.monotonic() - t < 5


def test_frame_processor_cancels_during_extraction(tmp_path):
    """Cancelling while FFmpeg is extracting stops it instead of waiting it out."""
    from videocraft.processors.frame_processor import FrameProcessor

    class Noop(FrameProcessor):
        def process_frame(self, frame_path, output_path, job):
            pass

    slow = tmp_path / "slow_ffmpeg"
    slow.write_text("#!/bin/sh\nsleep 30\n")
    slow.chmod(slow.stat().st_mode | stat.S_IEXEC)

    job = Job(source_path=tmp_path / "in.mp4", output_path=tmp_path / "o.mp4", pipeline=["denoiser"])
    threading.Timer(0.5, lambda: setattr(job, "cancelled", True)).start()

    t = time.monotonic()
    with patch("videocraft.processors.frame_processor.ffmpeg_cmd", return_value=str(slow)), \
         patch("videocraft.processors.frame_processor.ffprobe_fps", return_value="24"), \
         patch("videocraft.processors.frame_processor.ffprobe_duration", return_value=1.0):
        lines = list(Noop().process(job))

    assert time.monotonic() - t < 5
    assert any("cancelled" in l.lower() for l in lines)
    assert job.status != "failed"
