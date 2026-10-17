"""Tests for processors.upscaler — Real-ESRGAN upscaling."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from unittest.mock import patch, MagicMock
from videocraft.core.job import Job
from videocraft.processors.upscaler import UpscalerProcessor


def test_upscaler_creates():
    """UpscalerProcessor creates with no model loaded."""
    proc = UpscalerProcessor()
    assert proc._upsampler is None


def test_upscaler_model_selection():
    """select_model picks registry key, block count, and native scale."""
    sel = UpscalerProcessor.select_model
    assert sel({"scale": 4, "model": "RealESRGAN_x4plus"}) == ("realesrgan-x4plus", 23, 4)
    assert sel({"scale": 4, "model": "RealESRGAN_x4plus_anime"}) == ("realesrgan-x4plus-anime", 6, 4)
    assert sel({"scale": 2, "model": "RealESRGAN_x4plus"}) == ("realesrgan-x2plus", 23, 2)
    assert sel({}) == ("realesrgan-x4plus", 23, 4)


def test_upscaler_scale_factors():
    """Upscaler supports 2x and 4x scale factors."""
    proc = UpscalerProcessor()
    assert proc.get_scale_factor({"scale": "2x"}) == 2
    assert proc.get_scale_factor({"scale": "4x"}) == 4
    assert proc.get_scale_factor({}) == 4  # default


def test_upscaler_setup_falls_back_without_deps(tmp_path):
    """setup_model without ML deps → no upsampler, frames are copied."""
    proc = UpscalerProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
        params={"scale": "2x"},
    )

    proc.setup_model(job)  # cv2/basicsr/realesrgan not installed here
    assert proc._upsampler is None

    frame_in = tmp_path / "frame.png"
    frame_in.write_bytes(b"fakepng")
    frame_out = tmp_path / "frame_out.png"
    proc.process_frame(frame_in, frame_out, job)
    assert frame_out.read_bytes() == b"fakepng"  # copy fallback


def test_upscaler_setup_loads_model_once():
    """With mocked deps, setup_model builds one RealESRGANer for the job."""
    proc = UpscalerProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
        params={"scale": "4x"},
    )

    mock_realesrgan_mod = MagicMock()
    mock_basicsr_archs = MagicMock()
    mock_cv2 = MagicMock()
    mock_torch = MagicMock()

    mocks = {
        "realesrgan": mock_realesrgan_mod,
        "basicsr": MagicMock(),
        "basicsr.archs": mock_basicsr_archs,
        "basicsr.archs.rrdbnet_arch": mock_basicsr_archs.rrdbnet_arch,
        "cv2": mock_cv2,
        "torch": mock_torch,
    }

    with patch.dict("sys.modules", mocks):
        with patch("videocraft.processors.upscaler.ensure_model", return_value=Path("/tmp/fake.pth")):
            proc.setup_model(job)

    assert proc._upsampler is not None
    mock_realesrgan_mod.RealESRGANer.assert_called_once()
    # The configured compute device is passed through to Real-ESRGAN
    assert "device" in mock_realesrgan_mod.RealESRGANer.call_args.kwargs

    # Frames now go through the preloaded model
    proc._upsampler.enhance.return_value = (b"\x00" * 10, None)
    proc.process_frame(Path("/tmp/in.png"), Path("/tmp/out.png"), job)
    proc._upsampler.enhance.assert_called_once()

    proc.teardown_model()
    assert proc._upsampler is None


def test_upscaler_cancel_check():
    """Upscaler checks job.cancelled before processing."""
    proc = UpscalerProcessor()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
    )
    job.cancelled = True

    lines = list(proc.process(job))
    assert any("cancelled" in l.lower() for l in lines)


def test_upscaler_vram_settings():
    """Upscaler uses VRAMManager for batch/tile settings."""
    proc = UpscalerProcessor()
    from videocraft.processors.frame_processor import vram_manager
    batch = vram_manager.recommended_batch
    tile = vram_manager.recommended_tile
    assert batch >= 1
    assert tile >= 96
