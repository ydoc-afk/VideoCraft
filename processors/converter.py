"""FFmpeg format conversion processor."""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from core.ffmpeg import ffmpeg_cmd, ffprobe_cmd
from core.job import Job
from core.nvenc import video_encode_args
from processors.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

# Regex to extract time=HH:MM:SS.fff from FFmpeg stderr
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+[\.\d]+)")

# Container → default extension mapping
_CONTAINER_EXT = {
    "mp4": ".mp4",
    "mkv": ".mkv",
    "mov": ".mov",
    "avi": ".avi",
    "webm": ".webm",
    "gif": ".gif",
    "mp3": ".mp3",
    "aac": ".aac",
    "flac": ".flac",
    "wav": ".wav",
}

# Video codec mapping
_VIDEO_CODECS = {
    "h264": "libx264",
    "h265": "libx265",
    "av1": "libsvtav1",
    "vp9": "libvpx-vp9",
    "copy": "copy",
}

# Audio codec mapping
_AUDIO_CODECS = {
    "aac": "aac",
    "mp3": "libmp3lame",
    "flac": "flac",
    "pcm_s16le": "pcm_s16le",
    "copy": "copy",
    "opus": "libopus",
    "none": None,
}


def backup_existing(path: Path) -> None:
    """Rename existing output file with a timestamp suffix before overwrite."""
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_stem(f"{path.stem}_{ts}")
        path.rename(backup)
        logger.info("Backed up existing output: %s → %s", path, backup)


def ffprobe_duration(source: Path) -> float | None:
    """Get video duration in seconds via ffprobe."""
    try:
        cmd = [
            ffprobe_cmd(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(source),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError, OSError) as e:
        logger.warning("ffprobe failed: %s", e)
    return None


class ConverterProcessor(BaseProcessor):
    """FFmpeg format conversion processor.

    Handles container conversion, codec re-encoding, quality settings.
    CPU-only — no ML models needed.
    """

    def process(self, job: Job):
        """Run FFmpeg conversion, yielding log lines."""
        if job.cancelled:
            yield "[INFO] Job cancelled by user"
            return

        backup_existing(job.output_path)

        cmd = self._build_command(job)
        total_duration = ffprobe_duration(job.source_path)

        yield f"[INFO] Starting FFmpeg conversion: {job.source_path.name}"
        yield f"[INFO] Command: {' '.join(cmd[:10])}..."

        proc = None
        try:
            # Text mode: universal newlines turn FFmpeg's "\r"-terminated
            # status lines into separate lines, so progress updates (and
            # cancellation checks) happen per update, not once at the end.
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )

            stderr_raw = proc.stderr
            try:
                while True:
                    if job.cancelled:
                        yield "[INFO] Job cancelled by user"
                        return

                    line = stderr_raw.readline()
                    if not line:
                        break

                    # Parse progress from time= field
                    if total_duration:
                        seconds = self._parse_time(line)
                        if seconds is not None:
                            job.progress = min(seconds / total_duration, 1.0)
                            pct = int(job.progress * 100)
                            yield f"[FRAME] Progress: {pct}% ({self._format_time(seconds)}/{self._format_time(total_duration)})"
            finally:
                stderr_raw.close()

            proc.wait(timeout=300)

            if proc.returncode != 0 and not job.cancelled:
                yield f"[ERROR] FFmpeg exited with code {proc.returncode}"
                job.status = "failed"
            else:
                job.progress = 1.0
                yield f"[SUCCESS] Conversion complete: {job.output_path.name}"

        except subprocess.TimeoutExpired:
            yield "[ERROR] FFmpeg timed out"
            job.status = "failed"
        except Exception as e:
            yield f"[ERROR] Conversion failed: {e}"
            job.status = "failed"
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def _build_command(self, job: Job) -> list[str]:
        """Build FFmpeg command from job params."""
        params = job.params
        container = params.get("container", "mp4")
        video_codec = params.get("video_codec", "h264")
        audio_codec = params.get("audio_codec", "aac")
        crf = params.get("crf", 23)
        resolution = params.get("resolution")
        fps = params.get("fps")

        cmd = [
            ffmpeg_cmd(),
            "-y",
            "-hide_banner",
            "-loglevel", "info",
            "-i", str(job.source_path),
        ]

        # GIF can't hold H.264/AAC — let FFmpeg's gif encoder take over,
        # drop audio, and cap the frame rate to something GIF-sized.
        if container == "gif" or job.output_path.suffix.lower() == ".gif":
            vf = [f"scale={resolution}"] if resolution else []
            vf.append(f"fps={fps or 15}")
            cmd.extend(["-vf", ",".join(vf), "-an", str(job.output_path)])
            return cmd

        # WebM only holds VP8/VP9/AV1 video and Vorbis/Opus audio — swap in
        # compatible codecs rather than letting FFmpeg reject the mux.
        if container == "webm":
            if video_codec not in ("vp9", "av1", "copy"):
                video_codec = "vp9"
            if audio_codec in ("aac", "mp3", "flac", "pcm_s16le"):
                audio_codec = "opus"

        # Video filter (incompatible with stream copy — filters imply re-encode)
        vf_parts = []
        if video_codec != "copy":
            if resolution:
                vf_parts.append(f"scale={resolution}")
            if fps:
                vf_parts.append(f"fps={fps}")
        if vf_parts:
            cmd.extend(["-vf", ",".join(vf_parts)])

        # Video codec (-crf is meaningless for stream copy). video_encode_args
        # transparently swaps in the NVENC encoder + -cq when a usable NVIDIA
        # GPU is present, else falls back to the software encoder + -crf.
        enc = _VIDEO_CODECS.get(video_codec, video_codec)
        if enc == "copy":
            cmd.extend(["-c:v", "copy"])
        elif enc:
            cmd.extend(video_encode_args(video_codec, crf, enc))

        # Audio codec
        audio_enc = _AUDIO_CODECS.get(audio_codec)
        if audio_enc:
            cmd.extend(["-c:a", audio_enc])
        elif audio_codec == "none":
            cmd.append("-an")

        # Output
        cmd.append(str(job.output_path))
        return cmd

    @staticmethod
    def _parse_time(line: str) -> float | None:
        """Extract time=HH:MM:SS.fff as total seconds."""
        m = _TIME_RE.search(line)
        if not m:
            return None
        h, mn, s = m.groups()
        return int(h) * 3600 + int(mn) * 60 + float(s)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
