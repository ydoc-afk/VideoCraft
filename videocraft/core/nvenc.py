"""NVENC (NVIDIA hardware encoder) detection and codec selection.

An FFmpeg build can advertise NVENC encoders in `-encoders` and still fail
at runtime when there's no NVIDIA GPU/driver, the driver is too old, or the
codec isn't supported by the installed card (e.g. AV1 NVENC needs Ada
Lovelace). Listing is therefore not trustworthy — we probe each encoder with
a tiny throwaway encode to `null` and cache the verdict for the process.

Detection is fail-closed: any error (no ffmpeg, no GPU, timeout) means "not
available", so callers transparently fall back to the software encoder.

Processors should not build `-c:v` args by hand; call video_encode_args()
so NVENC is used consistently wherever it's viable.
"""

from __future__ import annotations

import logging
import subprocess
from functools import lru_cache

from videocraft.core.ffmpeg import ffmpeg_cmd

logger = logging.getLogger(__name__)

# Logical codec key → NVENC encoder name. VP9 has no NVENC encoder and is
# intentionally absent, so it always resolves to software.
NVENC_ENCODERS = {
    "h264": "h264_nvenc",
    "h265": "hevc_nvenc",
    "av1": "av1_nvenc",
}

# User preference (config gpu.use_nvenc). Independent of the hardware probe:
# flipping it must not invalidate the cached probe result, so it's checked
# separately at selection time rather than folded into the cache key.
_enabled = True


def set_nvenc_enabled(enabled: bool) -> None:
    """Enable/disable NVENC selection (from config gpu.use_nvenc).

    When disabled, every codec resolves to its software encoder regardless of
    what hardware is present.
    """
    global _enabled
    _enabled = bool(enabled)
    logger.debug("NVENC selection %s", "enabled" if _enabled else "disabled")


def is_enabled() -> bool:
    """Return whether NVENC selection is currently enabled by preference."""
    return _enabled


@lru_cache(maxsize=None)
def _nvenc_encoder_usable(encoder: str) -> bool:
    """Probe whether an NVENC encoder actually encodes on this machine.

    Runs a ~0.1s encode of a blank source to the null muxer. Cached per
    process, so the subprocess cost is paid at most once per encoder.
    """
    cmd = [
        ffmpeg_cmd(), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1",
        "-c:v", encoder, "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=20)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug("NVENC probe for %s failed: %s", encoder, e)
        return False

    if result.returncode == 0:
        logger.info("NVENC encoder available: %s", encoder)
        return True

    stderr = result.stderr.decode("utf-8", "replace")[-200:].strip()
    logger.debug("NVENC encoder %s not usable: %s", encoder, stderr)
    return False


def nvenc_encoder_for(codec: str) -> str | None:
    """Return the NVENC encoder for a logical codec, or None.

    None means "use software": either NVENC is disabled by preference, the
    codec has no NVENC encoder, or the probe found it unusable.
    """
    encoder = NVENC_ENCODERS.get(codec)
    if encoder and _enabled and _nvenc_encoder_usable(encoder):
        return encoder
    return None


def nvenc_available(codec: str) -> bool:
    """Return whether NVENC would be used for this codec right now."""
    return nvenc_encoder_for(codec) is not None


def nvenc_quality_args(quality: int, preset: str = "p5") -> list[str]:
    """Map a CRF-style quality (0–51, lower = better) to NVENC args.

    NVENC ignores -crf; constant-quality mode is `-rc vbr -cq N -b:v 0`
    (the 0 bitrate target removes the cap so CQ alone drives quality). The
    p1–p7 presets (p1 fastest … p7 slowest/best) are the modern NVENC preset
    scale; p5 is a balanced default.
    """
    q = max(0, min(51, int(quality)))
    return ["-preset", preset, "-rc", "vbr", "-cq", str(q), "-b:v", "0"]


def video_encode_args(
    codec: str,
    quality: int,
    software_encoder: str,
    preset: str = "p5",
) -> list[str]:
    """Build the `-c:v …` FFmpeg args for a codec, preferring NVENC.

    Falls back to `-c:v <software_encoder> -crf <quality>` when NVENC isn't
    available for `codec`. `codec` is the logical key ("h264"/"h265"/"av1"),
    `software_encoder` the libx*/libsvt* name to use otherwise.
    """
    hw = nvenc_encoder_for(codec)
    if hw:
        return ["-c:v", hw, *nvenc_quality_args(quality, preset)]
    return ["-c:v", software_encoder, "-crf", str(quality)]
