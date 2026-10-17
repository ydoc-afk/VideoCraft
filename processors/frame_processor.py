"""Frame processor base — shared frame extraction, inference, re-encoding."""

from __future__ import annotations

import glob
import logging
import re
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from core.ffmpeg import ffmpeg_cmd, ffprobe_cmd
from core.job import Job
from core.nvenc import video_encode_args
from core.vram_manager import vram_manager
from processors.base_processor import BaseProcessor
from processors.converter import ffprobe_duration

logger = logging.getLogger(__name__)

# yuv420p needs even width/height; odd-sized sources (kept as-is by the
# denoiser/colorizer) would otherwise fail the final encode.
_EVEN_DIMS_FILTER = "pad=ceil(iw/2)*2:ceil(ih/2)*2"

_FPS_RE = re.compile(r"^\d+(/\d+)?$")


def ffprobe_fps(source: Path) -> str | None:
    """Return the source frame rate as an FFmpeg rate string (e.g. "30000/1001")."""
    try:
        cmd = [
            ffprobe_cmd(), "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(source),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            rate = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
            if _FPS_RE.match(rate) and not rate.startswith("0"):
                return rate
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, IndexError) as e:
        logger.warning("ffprobe fps failed: %s", e)
    return None


class FrameProcessor(BaseProcessor, ABC):
    """Base class for frame-based ML processors.

    Handles:
    - Frame extraction via FFmpeg (native frame rate — no resampling)
    - Per-job model setup/teardown (models load once, not per frame)
    - Temp directory management
    - Progress tracking
    - Re-encoding frames to video at the source frame rate
    - VRAM cache clearing

    Subclasses implement setup_model() and process_frame().
    """

    def __init__(self) -> None:
        self._temp_dir: Path | None = None

    def process(self, job: Job):
        """Run the full frame-based pipeline.

        1. Clear VRAM cache
        2. Probe fps/duration, extract frames
        3. Load the model once (subclass setup_model)
        4. Process each frame (subclass process_frame)
        5. Re-encode to video at source fps
        6. Cleanup
        """
        vram_manager.clear_cache()

        if job.cancelled:
            yield "[INFO] Job cancelled by user"
            return

        try:
            # Note: the temp dir is cleaned up in _cleanup(), NOT added to
            # job.intermediate_files (that list is for step-output *files*
            # the worker chains between pipeline steps and unlinks).
            self._temp_dir = Path(tempfile.mkdtemp(prefix="videocraft_"))

            fps = ffprobe_fps(job.source_path) or "24"
            duration = ffprobe_duration(job.source_path) or 0.0
            yield f"[INFO] Source frame rate: {fps}"

            frame_pattern = str(self._temp_dir / "%06d.png")
            total_frames = self.extract_frames(job.source_path, frame_pattern, duration)

            if total_frames == 0:
                yield "[ERROR] No frames extracted from source"
                job.status = "failed"
                return

            yield f"[INFO] Extracted {total_frames} frames"

            # Load the model once for the whole job. ImportError inside
            # setup_model means missing optional ML deps → subclasses fall
            # back to copying frames; other errors fail the job.
            self.setup_model(job)

            # Process each frame
            output_pattern = str(self._temp_dir / "%06d_processed.png")
            processed = 0

            frame_files = sorted(glob.glob(str(self._temp_dir / "*.png")))
            for frame_in in frame_files:
                if job.cancelled:
                    yield "[INFO] Job cancelled by user"
                    return

                frame_in = Path(frame_in)
                frame_out = self._temp_dir / f"{frame_in.stem}_processed.png"

                yield f"[FRAME] Processing frame {processed + 1}/{total_frames}"
                self.process_frame(frame_in, frame_out, job)
                processed += 1

                # Update progress: 10% extraction + 90% processing
                job.progress = 0.1 + 0.9 * self._calc_progress(processed, total_frames)

            # Re-encode
            yield "[INFO] Re-encoding video..."
            if not self.reencode_video(
                input_pattern=output_pattern,
                output_path=job.output_path,
                source_path=job.source_path,
                fps=fps,
                duration=duration,
            ):
                yield "[ERROR] Re-encoding failed"
                job.status = "failed"
                return
            job.progress = 1.0
            yield f"[SUCCESS] Complete: {job.output_path.name}"

        except Exception as e:
            yield f"[ERROR] Processing failed: {e}"
            job.status = "failed"
        finally:
            self.teardown_model()
            vram_manager.clear_cache()
            self._cleanup()

    # ── Subclass hooks ──

    def setup_model(self, job: Job) -> None:
        """Load the inference model once per job. Override in subclasses."""

    def teardown_model(self) -> None:
        """Release the model after the job. Override if needed."""

    @abstractmethod
    def process_frame(self, frame_path: Path, output_path: Path, job: Job) -> None:
        """Process a single frame. Subclasses implement model inference here."""
        ...

    # ── FFmpeg steps ──

    def extract_frames(self, source: Path, pattern: str, duration: float = 0.0) -> int:
        """Extract all frames from video to a PNG sequence. Returns frame count."""
        cmd = [
            ffmpeg_cmd(), "-y", "-i", str(source),
            "-qscale:v", "1",
            pattern,
        ]
        timeout = max(300.0, duration * 20)
        logger.info("Extracting frames: %s", source.name)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error("FFmpeg extract failed: %s", result.stderr[-500:])
                return 0
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg extract timed out")
            return 0

        frames = sorted(glob.glob(str(Path(pattern).parent / "*.png")))
        return len(frames)

    def reencode_video(
        self,
        input_pattern: str,
        output_path: Path,
        source_path: Path,
        fps: str = "24",
        duration: float = 0.0,
    ) -> bool:
        """Re-encode frame sequence back to video at the source frame rate,
        muxing in the original audio."""
        cmd = [
            ffmpeg_cmd(), "-y",
            "-framerate", fps,
            "-i", input_pattern,
            "-i", str(source_path),
            # NVENC (h264_nvenc) when a usable GPU is present, else libx264.
            "-vf", _EVEN_DIMS_FILTER,
            *video_encode_args("h264", 18, "libx264"),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0?",
            str(output_path),
        ]
        timeout = max(600.0, duration * 30)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error("Re-encoding failed: %s", result.stderr[-500:])
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("Re-encoding timed out")
            return False

    @staticmethod
    def _calc_progress(processed: int, total: int) -> float:
        """Calculate progress as processed/total."""
        if total == 0:
            return 0.0
        return processed / total

    def _cleanup(self) -> None:
        """Clean up temp directory."""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.debug("Cleaned temp dir: %s", self._temp_dir)
        self._temp_dir = None

    @staticmethod
    def _build_extract_cmd(source: Path, frame_dir: Path, pattern: str) -> list[str]:
        """Build FFmpeg command for frame extraction."""
        return [
            ffmpeg_cmd(), "-y", "-i", str(source),
            "-qscale:v", "1",
            str(frame_dir / pattern),
        ]

    @staticmethod
    def _build_reencode_cmd(
        input_pattern: Path,
        output_pattern: Path,
        output_path: Path,
        source_path: Path,
        fps: str = "24",
    ) -> list[str]:
        """Build FFmpeg command for re-encoding."""
        return [
            ffmpeg_cmd(), "-y",
            "-framerate", fps,
            "-i", str(input_pattern),
            "-i", str(source_path),
            "-vf", _EVEN_DIMS_FILTER,
            *video_encode_args("h264", 18, "libx264"),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0?",
            str(output_path),
        ]
