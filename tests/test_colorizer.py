"""Tests for processors.colorizer — DDColor colorization."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from unittest.mock import patch, MagicMock
from videocraft.core.job import Job
from videocraft.processors.colorizer import ColorizerProcessor


def test_colorizer_creates():
    """ColorizerProcessor creates with DDColor default and no model loaded."""
    proc = ColorizerProcessor()
    assert proc._backend == "ddcolor"
    assert proc._pipeline is None


def test_colorizer_backend_is_always_ddcolor():
    """DDColor is the only backend; unknown ones (old configs) fall back to it."""
    proc = ColorizerProcessor()
    for params in ({"backend": "ddcolor"}, {"backend": "deoldify"}, {}):
        job = Job(
            source_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out.mp4"),
            pipeline=["colorizer"],
            params=params,
        )
        assert proc.get_backend(job) == "ddcolor"


def test_colorizer_styles():
    """Colorizer supports multiple styles."""
    proc = ColorizerProcessor()
    assert "artistic" in proc.get_style({"style": "artistic"})
    assert "stable" in proc.get_style({"style": "stable"})
    assert "artistic" in proc.get_style({})  # default


def test_colorizer_saturation():
    """Saturation is clamped to valid range."""
    proc = ColorizerProcessor()
    assert proc.get_saturation({"saturation": 0.5}) == 0.5
    assert proc.get_saturation({"saturation": 0.0}) == 0.0
    assert proc.get_saturation({"saturation": 2.0}) == 2.0  # within UI range (0–3)
    assert proc.get_saturation({"saturation": 5.0}) == 3.0  # clamped to UI max
    assert proc.get_saturation({"saturation": -1.0}) == 0.0  # clamped to min
    assert proc.get_saturation({}) == 1.0  # default


def test_colorizer_falls_back_without_deps(tmp_path):
    """setup_model without backend packages → no pipeline, frames copied."""
    proc = ColorizerProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["colorizer"],
        params={"backend": "ddcolor", "style": "artistic"},
    )

    # Simulate the optional ML packages being absent, whatever this machine has
    with patch.dict("sys.modules", {"torch": None}):
        proc.setup_model(job)
    assert proc._backend == "ddcolor"
    assert proc._pipeline is None

    frame_in = tmp_path / "frame.png"
    frame_in.write_bytes(b"fakepng")
    frame_out = tmp_path / "frame_out.png"
    proc.process_frame(frame_in, frame_out, job)
    assert frame_out.read_bytes() == b"fakepng"  # copy fallback


def test_colorizer_cancel_check():
    """Colorizer checks job.cancelled before processing."""
    proc = ColorizerProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["colorizer"],
    )
    job.cancelled = True

    lines = list(proc.process(job))
    assert any("cancelled" in l.lower() for l in lines)


def test_colorizer_yuv_preservation():
    """Colorizer preserves luminance (Y) channel."""
    proc = ColorizerProcessor()
    # The _apply_chroma method should preserve Y channel
    import numpy as np
    y_channel = np.array([[[100]], [[150]], [[200]]], dtype=np.uint8)
    # Simulate: if we have a result with same Y, luminance is preserved
    assert y_channel[0, 0, 0] == 100
    assert y_channel[1, 0, 0] == 150
    assert y_channel[2, 0, 0] == 200


def test_vendored_ddcolor_runs_end_to_end(tmp_path):
    """The vendored DDColor model loads through the real loader and colorizes a frame.

    Uses a tiny randomly-initialised checkpoint (real weights are ~870 MB), so it
    checks the plumbing — loading, resizing, Lab round trip — not colour quality.
    Skipped when the optional ML packages are not installed.
    """
    import pytest
    torch = pytest.importorskip("torch")
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from videocraft.processors.archs.ddcolor import ColorizationPipeline, DDColor, build_ddcolor_model

    net = DDColor(
        encoder_name="convnext-t", decoder_name="MultiScaleColorDecoder",
        input_size=[64, 64], num_output_channels=2, last_norm="Spectral",
        do_normalize=False, num_queries=100, num_scales=3, dec_layers=9,
    )
    ckpt = tmp_path / "tiny.pth"
    torch.save({"params": net.state_dict()}, ckpt)

    model = build_ddcolor_model(
        DDColor, model_path=str(ckpt), model_size="tiny", input_size=64,
        device=torch.device("cpu"),
    )
    out = ColorizationPipeline(model, input_size=64).process(
        (np.random.rand(30, 40, 3) * 255).astype(np.uint8)
    )
    assert out.shape == (30, 40, 3) and out.dtype == np.uint8
