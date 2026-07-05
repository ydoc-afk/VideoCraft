"""Tests for processors.converter — FFmpeg format conversion."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from datetime import datetime
from processors.converter import ConverterProcessor, backup_existing
from core.job import Job
import tempfile, shutil


def test_backup_existing_renames_file(tmp_path):
    """backup_existing renames existing file with timestamp suffix."""
    existing = tmp_path / "output.mp4"
    existing.write_text("old content")

    backup_existing(existing)

    assert existing.exists() is False  # original renamed
    backups = list(tmp_path.glob("output_*.mp4"))
    assert len(backups) == 1
    assert backups[0].read_text() == "old content"


def test_backup_existing_noop_when_missing(tmp_path):
    """backup_existing does nothing when file doesn't exist."""
    missing = tmp_path / "nope.mp4"
    backup_existing(missing)  # should not raise
    assert missing.exists() is False


def test_converter_builds_ffmpeg_command():
    """Converter builds correct FFmpeg command from job params.

    NVENC is forced unavailable so this exercises the software-encoder path
    deterministically regardless of the test machine's GPU.
    """
    proc = ConverterProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mkv"),
        pipeline=["converter"],
        params={
            "container": "mkv",
            "video_codec": "h265",
            "audio_codec": "aac",
            "crf": 23,
        },
    )
    with patch("core.nvenc.nvenc_encoder_for", return_value=None):
        cmd = proc._build_command(job)
    assert "ffmpeg" in cmd[0]
    assert "-y" in cmd
    assert str(job.source_path) in cmd
    assert str(job.output_path) in cmd
    assert "libx265" in cmd
    assert "aac" in cmd


def test_converter_uses_nvenc_when_available():
    """h265 resolves to hevc_nvenc + -cq when NVENC is available."""
    proc = ConverterProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mkv"),
        pipeline=["converter"],
        params={
            "container": "mkv",
            "video_codec": "h265",
            "audio_codec": "aac",
            "crf": 23,
        },
    )
    with patch("core.nvenc.nvenc_encoder_for", return_value="hevc_nvenc"):
        cmd = proc._build_command(job)
    assert "hevc_nvenc" in cmd
    assert "libx265" not in cmd
    assert "-cq" in cmd
    assert "-crf" not in cmd


def test_converter_progress_parsing():
    """Progress is extracted from FFmpeg stderr time= field."""
    proc = ConverterProcessor()
    # Simulate FFmpeg stderr line with time=
    line = "frame= 1000 fps= 30 q=24.0 size=   123456kB time=00:01:40.00 bitrate=10000.0kbits/s speed=1.2x"
    seconds = proc._parse_time(line)
    assert seconds is not None
    assert abs(seconds - 100.0) < 0.1  # 1:40 = 100 seconds


def test_converter_process_yields_lines():
    """Converter process() yields log lines for a job."""
    proc = ConverterProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )

    # Mock subprocess.Popen to avoid actually running FFmpeg
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    # stderr is a binary file-like object with readline()
    mock_stderr = MagicMock()
    mock_stderr.readline.side_effect = [
        b"ffmpeg version 5.0\n",
        b"frame= 100 fps= 30 time=00:00:10.00 bitrate=5000.0kbits/s\n",
        b"frame= 200 fps= 30 time=00:00:20.00 bitrate=5000.0kbits/s\n",
        b"",  # EOF
    ]
    mock_proc.stderr = mock_stderr
    mock_proc.wait.return_value = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        with patch("processors.converter.ffprobe_duration", return_value=20.0):
            # Command building probes NVENC via subprocess.run; stub it so the
            # globally-patched Popen isn't consumed by the probe.
            with patch("core.nvenc.nvenc_encoder_for", return_value=None):
                lines = list(proc.process(job))

    assert len(lines) >= 2
    assert any("Starting" in l for l in lines)
    assert job.progress >= 0.5  # At least some progress made


def test_converter_cancel_stops_subprocess():
    """Converter kills FFmpeg when job is cancelled."""
    proc = ConverterProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )
    job.cancelled = True

    mock_proc = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc):
        lines = list(proc.process(job))

    # Should have yielded a cancelled message
    assert any("cancelled" in l.lower() for l in lines)
