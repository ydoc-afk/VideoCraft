"""Tests for core.nvenc — NVENC detection and codec selection."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import subprocess

import videocraft.core.nvenc as nvenc


def setup_function(_):
    """Each test starts from a clean probe cache and enabled preference."""
    nvenc._nvenc_encoder_usable.cache_clear()
    nvenc.set_nvenc_enabled(True)


def _run_result(returncode: int):
    """Build a fake subprocess.run result."""
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=b"", stderr=b"")


def test_encoder_selected_when_probe_succeeds():
    """A usable NVENC encoder is chosen for its logical codec."""
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(0)) as run:
        assert nvenc.nvenc_encoder_for("h265") == "hevc_nvenc"
        assert nvenc.nvenc_available("h265") is True
    # Probe is cached — only one subprocess call despite two lookups
    assert run.call_count == 1


def test_falls_back_to_software_when_probe_fails():
    """A failed probe (non-zero exit) means software encoding."""
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(1)):
        assert nvenc.nvenc_encoder_for("h265") is None
        assert nvenc.nvenc_available("h265") is False


def test_probe_failclosed_when_ffmpeg_missing():
    """Missing ffmpeg binary is treated as 'not available', not an error."""
    with patch("videocraft.core.nvenc.subprocess.run", side_effect=FileNotFoundError):
        assert nvenc.nvenc_encoder_for("h264") is None


def test_probe_failclosed_on_timeout():
    """A hung probe is treated as unavailable."""
    with patch("videocraft.core.nvenc.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=20)):
        assert nvenc.nvenc_encoder_for("av1") is None


def test_disabled_preference_forces_software():
    """When disabled, no probe runs and software is always chosen."""
    nvenc.set_nvenc_enabled(False)
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(0)) as run:
        assert nvenc.nvenc_encoder_for("h265") is None
    run.assert_not_called()


def test_vp9_has_no_nvenc_encoder():
    """VP9 has no NVENC encoder and never probes."""
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(0)) as run:
        assert nvenc.nvenc_encoder_for("vp9") is None
    run.assert_not_called()


def test_quality_args_use_cq_not_crf():
    """NVENC quality maps to constant-quality args, clamped to 0–51."""
    args = nvenc.nvenc_quality_args(23)
    assert "-cq" in args and "23" in args
    assert "-crf" not in args
    assert "-b:v" in args
    # Out-of-range values are clamped
    assert "51" in nvenc.nvenc_quality_args(99)
    assert "0" in nvenc.nvenc_quality_args(-5)


def test_video_encode_args_hw_path():
    """video_encode_args emits the NVENC encoder + -cq when available."""
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(0)):
        args = nvenc.video_encode_args("h265", 20, "libx265")
    assert args[:2] == ["-c:v", "hevc_nvenc"]
    assert "-cq" in args and "-crf" not in args


def test_video_encode_args_software_path():
    """video_encode_args falls back to the software encoder + -crf."""
    with patch("videocraft.core.nvenc.subprocess.run", return_value=_run_result(1)):
        args = nvenc.video_encode_args("h265", 20, "libx265")
    assert args == ["-c:v", "libx265", "-crf", "20"]
