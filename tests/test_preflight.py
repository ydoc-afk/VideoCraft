"""Tests for ui.dialogs.preflight_dialog — pre-flight checks."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from pathlib import Path
from unittest.mock import patch, MagicMock
from videocraft.core.job import Job
from videocraft.core.job_queue import JobQueue
from videocraft.ui.dialogs.preflight_dialog import PreflightDialog, PreflightChecker


def test_preflight_checker_ffmpeg():
    """FFmpeg check returns True when found."""
    checker = PreflightChecker()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=b"ffmpeg version 6.0")
        result = checker.check_ffmpeg()
        assert result is True


def test_preflight_checker_ffmpeg_missing():
    """FFmpeg check returns False when not found."""
    checker = PreflightChecker()
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        result = checker.check_ffmpeg()
        assert result is False


def test_preflight_checker_cuda():
    """CUDA check returns correct status."""
    checker = PreflightChecker()

    # With CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    with patch.dict("sys.modules", {"torch": mock_torch}):
        result = checker.check_cuda()
        assert result is True

    # Without CUDA
    mock_torch2 = MagicMock()
    mock_torch2.cuda.is_available.return_value = False
    with patch.dict("sys.modules", {"torch": mock_torch2}):
        result = checker.check_cuda()
        assert result is False


def test_preflight_checker_disk_space():
    """Disk space check estimates output size."""
    checker = PreflightChecker()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )

    with patch("os.path.getsize", return_value=100_000_000):  # 100MB source
        result = checker.check_disk_space(job)
        assert result is True  # Should pass with plenty of disk


def test_preflight_checker_models(tmp_path):
    """Model check verifies required models exist (hermetic models dir)."""
    checker = PreflightChecker()

    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )
    job_ml = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
    )

    # Point the registry at an empty dir so locally installed models
    # don't leak into the test.
    with patch("videocraft.core.models_registry.get_models_dir", return_value=tmp_path):
        # Converter needs no models
        assert checker.check_models(job) is True
        # Upscaler needs at least one model — none present
        assert checker.check_models(job_ml) is False

        # Present model satisfies the check
        from videocraft.core.models_registry import MODELS
        (tmp_path / MODELS["realesrgan-x4plus"]["filename"]).write_bytes(b"x")
        assert checker.check_models(job_ml) is True


def test_preflight_dialog_creates():
    """PreflightDialog creates without crashing."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )
    dialog = PreflightDialog(job)
    assert dialog.windowTitle() == "Pre-flight Check"


def test_preflight_dialog_run_checks():
    """Running checks populates the results table."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )
    dialog = PreflightDialog(job)

    # Manually simulate check results instead of running async thread
    dialog._on_check_result("FFmpeg", "PASS", "Found")
    dialog._on_check_result("CUDA", "WARN", "CPU-only")
    dialog._on_check_result("Disk Space", "PASS", "OK")
    dialog._on_check_result("Models", "PASS", "OK")
    dialog._on_checks_done()

    # Table should have rows for each check
    assert dialog.results_table.rowCount() == 4
