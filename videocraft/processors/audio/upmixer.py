"""Audio upmixer — FFmpeg channel upmix (stereo → 5.1/7.1)."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from videocraft.core.ffmpeg import ffmpeg_cmd, with_threads
from videocraft.core.job import Job
from videocraft.processors.base_processor import BaseProcessor
from videocraft.processors.converter import backup_existing, ffprobe_duration

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+[\.\d]+)")

# Channel layout presets. FFmpeg's eac3 encoder supports at most 5.1 —
# feeding it 7.1 gets silently renegotiated back down to 6 channels, so
# 7.1 uses AAC (which encodes 8 channels).
_CHANNEL_LAYOUTS = {
    "5.1": {"layout": "5.1", "codec": "eac3", "default_bitrate": "640k"},
    "7.1": {"layout": "7.1", "codec": "aac", "default_bitrate": "640k"},
}


class AudioUpmixerProcessor(BaseProcessor):
    """FFmpeg channel upmix processor.

    Converts stereo audio to 5.1 or 7.1 surround sound.
    Settings:
        channel_layout: "5.1" | "7.1" (default: "5.1")
        bitrate: str, e.g. "640k" (default: "640k")
        lfe_gain: float, gain in dB applied to the LFE channel (default: 0.0)
    """

    def process(self, job: Job):
        """Run audio upmix, yielding log lines."""
        if job.cancelled:
            yield "[INFO] Job cancelled by user"
            return

        backup_existing(job.output_path)

        cmd = self._build_command(job)
        total_duration = ffprobe_duration(job.source_path)

        params = job.params
        layout = params.get("channel_layout", "5.1")
        bitrate = params.get("bitrate", "640k")

        yield f"[INFO] Starting audio upmix: {job.source_path.name}"
        yield f"[INFO] Target: {layout}, Bitrate: {bitrate}"
        yield f"[INFO] Command: {' '.join(cmd[:10])}..."

        proc = None
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
            )

            for line in proc.stderr:  # type: ignore
                if job.cancelled:
                    yield "[INFO] Job cancelled by user"
                    return

                if total_duration:
                    seconds = _parse_time(line)
                    if seconds is not None:
                        job.progress = min(seconds / total_duration, 1.0)
                        pct = int(job.progress * 100)
                        yield f"[FRAME] Progress: {pct}% ({_format_time(seconds)}/{_format_time(total_duration)})"

            proc.wait(timeout=300)

            if proc.returncode != 0 and not job.cancelled:
                yield f"[ERROR] FFmpeg exited with code {proc.returncode}"
                job.status = "failed"
            else:
                job.progress = 1.0
                yield f"[SUCCESS] Audio upmix complete: {job.output_path.name}"

        except subprocess.TimeoutExpired:
            yield "[ERROR] FFmpeg timed out"
            job.status = "failed"
        except Exception as e:
            yield f"[ERROR] Audio upmix failed: {e}"
            job.status = "failed"
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    @staticmethod
    def _pan_filter(target_layout: str, lfe_gain_db: float) -> str:
        """Build a pan filter for stereo → surround upmix.

        Only references FL/FR — the input is downmixed to stereo channel
        names, so referencing FC (absent in stereo) would make pan fail.
        The LFE gain is folded into the LFE coefficients (there is no
        FFmpeg filter that adjusts a single channel's gain after pan).
        """
        lfe = 0.354 * (10 ** (lfe_gain_db / 20.0))  # -3dB sum, adjusted by user gain
        lfe_expr = f"LFE={lfe:.4f}*FL+{lfe:.4f}*FR"

        if target_layout == "5.1":
            return (
                "pan=5.1"
                "|FL=FL"
                "|FR=FR"
                "|FC=0.5*FL+0.5*FR"
                f"|{lfe_expr}"
                "|BL=0.5*FL"
                "|BR=0.5*FR"
            )
        # 7.1 = FL FR FC LFE BL BR SL SR
        return (
            "pan=7.1"
            "|FL=FL"
            "|FR=FR"
            "|FC=0.5*FL+0.5*FR"
            f"|{lfe_expr}"
            "|BL=0.35*FL"
            "|BR=0.35*FR"
            "|SL=0.5*FL"
            "|SR=0.5*FR"
        )

    def _build_command(self, job: Job) -> list[str]:
        """Build FFmpeg upmix command."""
        params = job.params
        layout_name = params.get("channel_layout", "5.1")
        bitrate = params.get("bitrate", "640k")
        lfe_gain = float(params.get("lfe_gain", 0.0))

        layout_info = _CHANNEL_LAYOUTS.get(layout_name, _CHANNEL_LAYOUTS["5.1"])
        target_layout = layout_info["layout"]
        codec = layout_info["codec"]

        # Normalize any input to stereo channel names first so the pan
        # expressions are always valid, then upmix.
        af = "aformat=channel_layouts=stereo," + self._pan_filter(target_layout, lfe_gain)

        cmd = [
            ffmpeg_cmd(),
            "-y",
            "-hide_banner",
            "-loglevel", "info",
            "-i", str(job.source_path),
            "-c:v", "copy",
            "-af", af,
            "-c:a", codec,
            "-b:a", bitrate,
            str(job.output_path),
        ]
        return with_threads(cmd)


def _parse_time(line: str) -> float | None:
    """Extract time=HH:MM:SS.fff as total seconds."""
    m = _TIME_RE.search(line)
    if not m:
        return None
    h, mn, s = m.groups()
    return int(h) * 3600 + int(mn) * 60 + float(s)


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
