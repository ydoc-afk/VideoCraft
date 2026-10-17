"""Tests for processors.denoiser — SCUNet denoising."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from unittest.mock import patch, MagicMock
from videocraft.core.job import Job
from videocraft.processors.denoiser import DenoiserProcessor


def test_denoiser_creates():
    """DenoiserProcessor creates with no model loaded."""
    proc = DenoiserProcessor()
    assert proc._net is None


def test_denoiser_model_key():
    """Model param maps to registry keys (including legacy values)."""
    assert DenoiserProcessor.model_key({"model": "scunet-color-real"}) == "scunet-color-real"
    assert DenoiserProcessor.model_key({"model": "scunet-color-gaussian"}) == "scunet-color-gaussian"
    assert DenoiserProcessor.model_key({"model": "scunet_color_real_psnr"}) == "scunet-color-real"
    assert DenoiserProcessor.model_key({}) == "scunet-color-real"


def test_denoiser_falls_back_without_deps(tmp_path):
    """setup_model without ML deps → no net, frames are copied."""
    proc = DenoiserProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["denoiser"],
    )

    proc.setup_model(job)  # torch/cv2 not installed here
    assert proc._net is None

    frame_in = tmp_path / "frame.png"
    frame_in.write_bytes(b"fakepng")
    frame_out = tmp_path / "frame_out.png"
    proc.process_frame(frame_in, frame_out, job)
    assert frame_out.read_bytes() == b"fakepng"  # copy fallback


def test_denoiser_cancel_check():
    """Denoiser checks job.cancelled before processing."""
    proc = DenoiserProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["denoiser"],
    )
    job.cancelled = True

    lines = list(proc.process(job))
    assert any("cancelled" in l.lower() for l in lines)
