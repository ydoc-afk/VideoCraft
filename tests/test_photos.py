"""Photo support: the frame-based tools accept still images."""

import subprocess
import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from videocraft.core.job import Job
from videocraft.core.media import IMAGE_TOOLS, is_image, is_media, open_dialog_filter
from videocraft.processors.frame_processor import FrameProcessor

ffmpeg_available = subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
needs_ffmpeg = pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")


class _CopyThrough(FrameProcessor):
    def process_frame(self, frame_path, output_path, job):
        output_path.write_bytes(frame_path.read_bytes())


def _make_photo(path: Path, size="33x21") -> None:
    """A small test photo with odd dimensions (unlike video, photos allow them)."""
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=s={size}:d=1",
         "-frames:v", "1", str(path)],
        check=True,
    )


def _size(path: Path) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return out.replace(",", "x")


def test_media_helpers():
    assert is_image("a/b/Photo.JPG") and is_image(Path("x.png")) and not is_image("clip.mp4")
    assert is_media("x.webp") and is_media("clip.mkv") and is_media("song.flac") and not is_media("notes.txt")
    assert IMAGE_TOOLS == {"upscaler", "denoiser", "colorizer"}
    assert "*.jpg" in open_dialog_filter() and "*.mp4" in open_dialog_filter()


@needs_ffmpeg
@pytest.mark.parametrize("ext", [".jpg", ".png"])
def test_photo_goes_through_frame_pipeline(tmp_path, ext):
    src = tmp_path / f"in{ext}"
    out = tmp_path / f"out{ext}"
    _make_photo(src)
    job = Job(source_path=src, output_path=out, pipeline=["denoiser"])

    lines = list(_CopyThrough().process(job))

    assert job.status != "failed", lines
    assert any("photo" in l.lower() for l in lines)
    assert out.exists() and _size(out) == "33x21"      # odd size preserved, format kept
    assert job.progress == 1.0


@needs_ffmpeg
def test_photo_output_is_backed_up_not_overwritten(tmp_path):
    src, out = tmp_path / "in.png", tmp_path / "out.png"
    _make_photo(src)
    out.write_bytes(b"old")
    list(_CopyThrough().process(Job(source_path=src, output_path=out, pipeline=["denoiser"])))
    assert len(list(tmp_path.glob("out_*.png"))) == 1


def test_photo_skips_video_probing(tmp_path):
    """A photo must not be probed for fps/duration (they don't exist for stills)."""
    src, out = tmp_path / "in.jpg", tmp_path / "out.jpg"
    src.write_bytes(b"x")
    job = Job(source_path=src, output_path=out, pipeline=["denoiser"])
    with patch("videocraft.processors.frame_processor.ffprobe_fps") as fps, \
         patch("videocraft.processors.frame_processor.ffprobe_duration") as dur, \
         patch.object(_CopyThrough, "extract_frames", return_value=0):
        list(_CopyThrough().process(job))
    fps.assert_not_called()
    dur.assert_not_called()


def test_main_window_queues_photos_only_for_image_tools():
    from videocraft.ui.main_window import MainWindow

    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    win.output_panel.set_output_dir(Path("/tmp/output"))
    logs = []
    win.append_log = logs.append

    win.tools_panel.tab_widget.setCurrentIndex(5)          # Convert: video/audio only
    win._add_to_queue(Path("/tmp/holiday.jpg"))
    assert win.queue.jobs == [] and any("photos work" in l for l in logs)

    win.tools_panel.tab_widget.setCurrentIndex(0)          # Upscaler
    win._add_to_queue(Path("/tmp/holiday.JPG"))
    job = win.queue.jobs[0]
    assert job.pipeline == ["upscaler"] and job.output_path.suffix == ".JPG"
    assert job.output_path.parent == Path("/tmp/output")
