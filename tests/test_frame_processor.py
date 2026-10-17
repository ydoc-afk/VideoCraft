"""Tests for processors.frame_processor — shared frame extraction/re-encoding."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from core.job import Job
from processors.frame_processor import FrameProcessor


def test_frame_processor_is_abstract():
    """FrameProcessor cannot be instantiated directly."""
    try:
        FrameProcessor()
        assert False, "Should raise TypeError"
    except TypeError:
        pass


def test_extract_frames_command():
    """_build_extract_cmd builds correct FFmpeg command."""
    proc = _make_proc()
    cmd = proc._build_extract_cmd(Path("/tmp/in.mp4"), Path("/tmp/frames"), "%06d.png")
    assert "ffmpeg" in cmd[0].lower()
    assert str(Path("/tmp/in.mp4")) in cmd
    assert str(Path("/tmp/frames")) in cmd or "%06d.png" in " ".join(cmd)


def test_reencode_command():
    """_build_reencode_cmd builds correct FFmpeg command."""
    proc = _make_proc()
    cmd = proc._build_reencode_cmd(
        Path("/tmp/frames/%06d.png"),
        Path("/tmp/frames/%06d_upscaled.png"),
        Path("/tmp/out.mp4"),
        Path("/tmp/in.mp4"),
    )
    assert "ffmpeg" in cmd[0].lower()
    assert "-i" in cmd


def test_progress_calculation():
    """Progress is calculated as processed/total."""
    proc = _make_proc()
    # Simulate 5 of 20 frames done
    progress = proc._calc_progress(5, 20)
    assert progress == 0.25

    # Edge: 0 total
    progress = proc._calc_progress(0, 0)
    assert progress == 0.0


def test_cancel_check_in_process():
    """Process stops early when job.cancelled is True."""
    proc = _make_proc()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
    )
    job.cancelled = True

    # Mock extract_frames to return immediately
    with patch.object(proc, "extract_frames", return_value=0):
        lines = list(proc.process(job))
        assert any("cancelled" in l.lower() for l in lines)


def test_vram_cache_clear():
    """clear_vram_cache is called before and after processing."""
    proc = _make_proc()
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["upscaler"],
    )

    with patch("processors.frame_processor.vram_manager") as mock_vram:
        with patch.object(proc, "extract_frames", return_value=0):
            list(proc.process(job))
            # clear_cache should have been called
            assert mock_vram.clear_cache.called


def _make_proc():
    """Create a concrete FrameProcessor for testing."""
    class TestProcessor(FrameProcessor):
        def process_frame(self, frame_path, output_path, job):
            pass
    return TestProcessor()


def test_reencode_cmd_pads_to_even_dimensions():
    """yuv420p needs even dimensions, so the re-encode pads odd-sized frames."""
    from processors.frame_processor import FrameProcessor
    from pathlib import Path
    cmd = FrameProcessor._build_reencode_cmd(
        Path("in/%06d.png"), Path("out"), Path("o.mp4"), Path("s.mp4"),
    )
    assert cmd[cmd.index("-vf") + 1] == "pad=ceil(iw/2)*2:ceil(ih/2)*2"


def test_frame_processor_backs_up_existing_output(tmp_path):
    """An existing output file is renamed, not silently overwritten."""
    from unittest.mock import patch
    from core.job import Job
    from processors.frame_processor import FrameProcessor

    class Copy(FrameProcessor):
        def process_frame(self, frame_path, output_path, job):
            output_path.write_bytes(frame_path.read_bytes())

    out = tmp_path / "clip_output.mp4"
    out.write_bytes(b"old result")
    job = Job(source_path=tmp_path / "in.mp4", output_path=out, pipeline=["denoiser"])

    def fake_extract(self, source, pattern, duration=0.0):
        (Path(pattern).parent / "000001.png").write_bytes(b"x")
        return 1

    def fake_reencode(self, **kw):
        kw["output_path"].write_bytes(b"new result")
        return True

    with patch.object(Copy, "extract_frames", fake_extract), \
         patch.object(Copy, "reencode_video", fake_reencode), \
         patch("processors.frame_processor.ffprobe_fps", return_value="24"), \
         patch("processors.frame_processor.ffprobe_duration", return_value=1.0):
        list(Copy().process(job))

    assert out.read_bytes() == b"new result"
    backups = [p for p in tmp_path.glob("clip_output_*.mp4")]
    assert len(backups) == 1 and backups[0].read_bytes() == b"old result"
