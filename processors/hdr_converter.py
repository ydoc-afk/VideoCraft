"""HDR converter — SDR→HDR10 via FFmpeg zscale + tonemap filters."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from core.ffmpeg import ffmpeg_cmd
from core.job import Job
from processors.base_processor import BaseProcessor
from processors.converter import backup_existing, ffprobe_duration

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+[\.\d]+)")

# Tonemap algorithms supported by FFmpeg
_TONEMAP_ALGOS = {"hable", "reinhard", "mobius"}

# HDR target formats
_HDR_FORMATS = {"hdr10", "hlg"}


class HDRConverterProcessor(BaseProcessor):
    """SDR→HDR10 converter using FFmpeg zscale + tonemap.

    No ML model needed — pure FFmpeg filter chain.
    Settings:
        hdr_format: "hdr10" | "hlg" (default: "hdr10")
        peak_nits: int (default: 1000)
        tonemap: "hable" | "reinhard" | "mobius" (default: "hable")
    """

    def process(self, job: Job):
        """Run HDR conversion, yielding log lines."""
        if job.cancelled:
            yield "[INFO] Job cancelled by user"
            return

        backup_existing(job.output_path)

        cmd = self._build_command(job)
        total_duration = ffprobe_duration(job.source_path)

        params = job.params
        hdr_format = params.get("hdr_format", "hdr10")
        peak_nits = params.get("peak_nits", 1000)

        yield f"[INFO] Starting HDR conversion: {job.source_path.name}"
        yield f"[INFO] Target: {hdr_format.upper()}, Peak: {peak_nits} nits"
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
                yield f"[SUCCESS] HDR conversion complete: {job.output_path.name}"

        except subprocess.TimeoutExpired:
            yield "[ERROR] FFmpeg timed out"
            job.status = "failed"
        except Exception as e:
            yield f"[ERROR] HDR conversion failed: {e}"
            job.status = "failed"
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def _build_command(self, job: Job) -> list[str]:
        """Build FFmpeg SDR→HDR conversion command.

        The chain linearizes the SDR signal (assumed BT.709), converts to
        BT.2020 primaries, then encodes with the HDR transfer function (PQ
        for HDR10, HLG otherwise). SDR reference white is mapped to 203
        nits per BT.2408. Note: the `tonemap` filter is HDR→SDR and has no
        place in this direction; peak_nits only feeds the HDR10 metadata.
        """
        params = job.params
        hdr_format = params.get("hdr_format", "hdr10")
        peak_nits = int(params.get("peak_nits", 1000))

        if hdr_format not in _HDR_FORMATS:
            hdr_format = "hdr10"

        target_trc = "smpte2084" if hdr_format == "hdr10" else "arib-std-b67"
        # SDR (BT.709) → linear @ 203 nits ref white → BT.2020 + HDR transfer.
        # setparams declares the input as BT.709/TV-range first — untagged
        # sources otherwise make zscale fail with "no path between
        # colorspaces".
        vf = (
            "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv,"
            "zscale=t=linear:npl=203,"
            "format=gbrpf32le,"
            f"zscale=p=bt2020:t={target_trc}:m=bt2020nc:r=tv,"
            "format=yuv420p10le"
        )

        x265_common = "colorprim=bt2020:colormatrix=bt2020nc:range=limited"
        if hdr_format == "hdr10":
            x265_params = (
                f"{x265_common}:transfer=smpte2084:hdr10=1"
                f":max-cll={peak_nits},{max(peak_nits // 10, 50)}"
            )
        else:
            x265_params = f"{x265_common}:transfer=arib-std-b67"

        cmd = [
            ffmpeg_cmd(),
            "-y",
            "-hide_banner",
            "-loglevel", "info",
            "-i", str(job.source_path),
            "-vf", vf,
            "-color_primaries", "bt2020",
            "-color_trc", target_trc,
            "-colorspace", "bt2020nc",
            # HDR stays on software x265 by design: the HDR10 SEI metadata
            # (mastering display, max-cll) is emitted via -x265-params, which
            # hevc_nvenc does not accept. NVENC HDR would need a different
            # metadata path, so we don't swap it in here to avoid producing
            # files with missing/incorrect HDR signalling.
            "-c:v", "libx265",
            "-crf", "20",
            "-x265-params", x265_params,
            "-c:a", "copy",
            str(job.output_path),
        ]
        return cmd


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
