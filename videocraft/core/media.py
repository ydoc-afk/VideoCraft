"""Supported media types — one place for the file-extension lists."""

from __future__ import annotations

from pathlib import Path

VIDEO_EXTS = frozenset({".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg"})
AUDIO_EXTS = frozenset({".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"})
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS

# Tools that can process a still image (they work frame by frame, and a photo
# is a single frame). The rest need video or audio.
IMAGE_TOOLS = frozenset({"upscaler", "denoiser", "colorizer"})


def is_image(path: Path | str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def is_media(path: Path | str) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTS


def _globs(exts) -> str:
    return " ".join(f"*{e}" for e in sorted(exts))


def open_dialog_filter() -> str:
    """Qt file-dialog filter string covering all supported types."""
    return (
        f"Media Files ({_globs(MEDIA_EXTS)});;"
        f"Video Files ({_globs(VIDEO_EXTS)});;"
        f"Audio Files ({_globs(AUDIO_EXTS)});;"
        f"Photos ({_globs(IMAGE_EXTS)})"
    )
