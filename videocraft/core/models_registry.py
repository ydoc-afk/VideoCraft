"""Canonical model registry — single source of truth for ML model weights.

Every component (processors, pre-flight checks, Model Manager dialog) must
resolve model files through this module so filenames and locations agree.

Notes:
- Filenames match the upstream release names so manually downloaded files
  are picked up as-is.
- sha256 is optional; None skips verification (upstream projects do not
  publish official digests). All URLs verified live 2026-07-04.
- Demucs (vocal remover) is absent on purpose: it downloads and caches its
  own weights via torch hub on first run.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

import requests

from videocraft.core.config import AppConfig
from videocraft.core.hf_auth import AUTH_STATUSES, DownloadAuthError, auth_headers, is_hf_url

logger = logging.getLogger(__name__)

# key → metadata. "tool" links a model to the pipeline tool that uses it.
MODELS: dict[str, dict] = {
    "realesrgan-x4plus": {
        "display": "RealESRGAN x4plus (General, 4x)",
        "tool": "upscaler",
        "size_mb": 64,
        "filename": "RealESRGAN_x4plus.pth",
        "urls": [
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        ],
        "sha256": None,
    },
    "realesrgan-x2plus": {
        "display": "RealESRGAN x2plus (General, 2x)",
        "tool": "upscaler",
        "size_mb": 64,
        "filename": "RealESRGAN_x2plus.pth",
        "urls": [
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        ],
        "sha256": None,
    },
    "realesrgan-x4plus-anime": {
        "display": "RealESRGAN x4plus Anime 6B (4x)",
        "tool": "upscaler",
        "size_mb": 18,
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "urls": [
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        ],
        "sha256": None,
    },
    "scunet-color-real": {
        "display": "SCUNet (Color, real-world noise)",
        "tool": "denoiser",
        "size_mb": 69,
        "filename": "scunet_color_real_psnr.pth",
        "urls": [
            "https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_real_psnr.pth",
        ],
        "sha256": None,
    },
    "scunet-color-gaussian": {
        "display": "SCUNet (Color, Gaussian noise σ25)",
        "tool": "denoiser",
        "size_mb": 69,
        "filename": "scunet_color_25.pth",
        "urls": [
            "https://github.com/cszn/KAIR/releases/download/v1.0/scunet_color_25.pth",
        ],
        "sha256": None,
    },
    "ddcolor-artistic": {
        "display": "DDColor (Artistic)",
        "tool": "colorizer",
        "size_mb": 875,
        "filename": "ddcolor_artistic.pth",
        "urls": [
            "https://huggingface.co/piddnad/DDColor-models/resolve/main/ddcolor_artistic.pth",
        ],
        "sha256": None,
    },
    "ddcolor-modelscope": {
        "display": "DDColor (ModelScope)",
        "tool": "colorizer",
        "size_mb": 875,
        "filename": "ddcolor_modelscope.pth",
        "urls": [
            "https://huggingface.co/piddnad/DDColor-models/resolve/main/ddcolor_modelscope.pth",
        ],
        "sha256": None,
    },
}


def get_models_dir() -> Path:
    """Return the canonical models directory.

    <user data dir>/models (e.g. ~/.local/share/videocraft/models), or the
    folder named by $VIDEOCRAFT_MODELS_DIR.
    """
    override = os.environ.get("VIDEOCRAFT_MODELS_DIR")
    if override:
        return Path(override)
    return AppConfig.platform_data_dir() / "models"


def model_path(key: str) -> Path:
    """Return the canonical file path for a model key."""
    return get_models_dir() / MODELS[key]["filename"]


def find_model(key: str) -> Path | None:
    """Return the model file path if it exists locally, else None."""
    path = model_path(key)
    return path if path.exists() else None


def keys_for_tool(tool: str) -> list[str]:
    """Return all registry keys belonging to a tool."""
    return [k for k, m in MODELS.items() if m["tool"] == tool]


def verify_sha256(path: Path, expected: str | None) -> bool:
    """Verify a file's sha256; a None digest passes (no official digest)."""
    if not expected:
        return True
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest() == expected


def ensure_model(key: str) -> Path:
    """Return the model path, downloading it if missing.

    Downloads go to a .part file first and are renamed only on success,
    so an interrupted download never masquerades as an installed model.
    Raises FileNotFoundError if the model can't be obtained.
    """
    path = model_path(key)
    if path.exists():
        return path

    meta = MODELS[key]
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")

    auth_error: DownloadAuthError | None = None
    for url in meta["urls"]:
        try:
            logger.info("Downloading %s from %s", key, url)
            # requests drops the Authorization header on a cross-host redirect
            # (Hugging Face redirects to its CDN), so the token stays on HF.
            with requests.get(
                url, stream=True, timeout=60, headers=auth_headers(url)
            ) as resp:
                if resp.status_code in AUTH_STATUSES and is_hf_url(url):
                    auth_error = DownloadAuthError(resp.status_code, url)
                    continue
                resp.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            if not verify_sha256(part, meta.get("sha256")):
                logger.warning("Checksum mismatch for %s from %s", key, url)
                part.unlink(missing_ok=True)
                continue
            part.rename(path)
            return path
        except (requests.RequestException, OSError) as e:
            logger.warning("Download failed from %s: %s", url, e)
            part.unlink(missing_ok=True)

    if auth_error is not None:
        raise auth_error

    raise FileNotFoundError(
        f"Model '{key}' ({meta['filename']}) not found and could not be "
        f"downloaded. Get it manually from: {meta['urls']} and place it in "
        f"{get_models_dir()}"
    )
