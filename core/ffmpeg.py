"""Shared FFmpeg/ffprobe binary resolution.

main.py detects the FFmpeg binary at startup (bundled → PATH) and the
Settings dialog can override it; both call set_ffmpeg_path(). Processors
and panels must use ffmpeg_cmd()/ffprobe_cmd() instead of hardcoding
"ffmpeg"/"ffprobe" so the bundled or user-configured binary is honored.
"""

from __future__ import annotations

from pathlib import Path

_ffmpeg_path: str = "ffmpeg"


def set_ffmpeg_path(path: str | Path) -> None:
    """Set the FFmpeg binary used by all processors."""
    global _ffmpeg_path
    _ffmpeg_path = str(path)


def ffmpeg_cmd() -> str:
    """Return the FFmpeg executable (path or bare command)."""
    return _ffmpeg_path


def ffprobe_cmd() -> str:
    """Return the ffprobe executable, preferring one next to ffmpeg."""
    p = Path(_ffmpeg_path)
    if p.name != "ffmpeg" and "ffmpeg" in p.name:
        sibling = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
        if sibling.exists():
            return str(sibling)
    elif p.is_absolute():
        sibling = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
        if sibling.exists():
            return str(sibling)
    return "ffprobe"
