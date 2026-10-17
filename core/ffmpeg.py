"""Shared FFmpeg/ffprobe binary resolution.

main.py detects the FFmpeg binary at startup (bundled → PATH) and the
Settings dialog can override it; both call set_ffmpeg_path(). Processors
and panels must use ffmpeg_cmd()/ffprobe_cmd() instead of hardcoding
"ffmpeg"/"ffprobe" so the bundled or user-configured binary is honored.
"""

from __future__ import annotations

from pathlib import Path

_ffmpeg_path: str = "ffmpeg"
_threads: int = 0  # 0 = let FFmpeg decide


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


def set_threads(count: int) -> None:
    """Set the FFmpeg encoder thread count (0 = auto)."""
    global _threads
    _threads = max(0, int(count))


def with_threads(cmd: list[str]) -> list[str]:
    """Insert `-threads N` before the output file (last arg) when configured."""
    if _threads <= 0:
        return cmd
    return [*cmd[:-1], "-threads", str(_threads), cmd[-1]]
