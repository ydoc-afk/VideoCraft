"""TOML config system — load/save user settings with platform-specific paths."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class GeneralConfig:
    theme: str = "dark_amber.xml"  # a theme qt-material actually ships
    default_output_dir: str = ""
    concurrent_jobs: int = 1


@dataclass
class FFmpegConfig:
    path: str = "ffmpeg"
    threads: int = 0


@dataclass
class GPUConfig:
    device: str = "auto"  # auto | cuda:0 | cpu
    tile_size: int = 0  # 0 = Auto (detect from VRAM); >0 = manual override
    use_nvenc: bool = True  # prefer NVIDIA hardware encoding when available


@dataclass
class UpscalerConfig:
    default_scale: int = 4
    default_model: str = "RealESRGAN_x4plus"


@dataclass
class ColorizerConfig:
    default_style: str = "artistic"
    saturation: float = 1.0
    backend: str = "ddcolor"  # ddcolor | deoldify


@dataclass
class HDRConfig:
    peak_nits: int = 1000


@dataclass
class AppConfig:
    """Top-level application configuration."""

    general: GeneralConfig = field(default_factory=GeneralConfig)
    ffmpeg: FFmpegConfig = field(default_factory=FFmpegConfig)
    gpu: GPUConfig = field(default_factory=GPUConfig)
    upscaler: UpscalerConfig = field(default_factory=UpscalerConfig)
    colorizer: ColorizerConfig = field(default_factory=ColorizerConfig)
    hdr: HDRConfig = field(default_factory=HDRConfig)

    @classmethod
    def defaults(cls) -> AppConfig:
        """Return a fresh config with all default values."""
        return cls()

    @classmethod
    def load(cls, path: Path) -> AppConfig:
        """Load config from a TOML file. Returns defaults if file missing."""
        if not path.exists():
            return cls.defaults()

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        with open(path, "rb") as f:
            data: dict[str, Any] = tomllib.load(f)

        cfg = cls()
        if "general" in data:
            for k, v in data["general"].items():
                if hasattr(cfg.general, k):
                    setattr(cfg.general, k, v)
        if "ffmpeg" in data:
            for k, v in data["ffmpeg"].items():
                if hasattr(cfg.ffmpeg, k):
                    setattr(cfg.ffmpeg, k, v)
        if "gpu" in data:
            for k, v in data["gpu"].items():
                if hasattr(cfg.gpu, k):
                    setattr(cfg.gpu, k, v)
        if "upscaler" in data:
            for k, v in data["upscaler"].items():
                if hasattr(cfg.upscaler, k):
                    setattr(cfg.upscaler, k, v)
        if "colorizer" in data:
            for k, v in data["colorizer"].items():
                if hasattr(cfg.colorizer, k):
                    setattr(cfg.colorizer, k, v)
        if "hdr" in data:
            for k, v in data["hdr"].items():
                if hasattr(cfg.hdr, k):
                    setattr(cfg.hdr, k, v)
        return cfg

    def save(self, path: Path) -> None:
        """Save config to a TOML file.

        Uses tomli-w for serialization — the previous hand-rolled writer
        did not escape backslashes/quotes, so a Windows path in any string
        field produced a config file that could not be parsed back.
        """
        import tomli_w

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            tomli_w.dump(asdict(self), f)

    @staticmethod
    def platform_config_dir() -> Path:
        """Return platform-specific config directory."""
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "VideoCraft"
        elif sys.platform == "win32":
            return Path(os.environ.get("APPDATA", str(Path.home()))) / "VideoCraft"
        else:
            # Keep the historical "videocraftapp" name — existing installs
            # already have configs there — but honor XDG_CONFIG_HOME.
            xdg = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg) if xdg else Path.home() / ".config"
            return base / "videocraftapp"

    @staticmethod
    def platform_config_path() -> Path:
        """Return full path to config.toml on this platform."""
        return AppConfig.platform_config_dir() / "config.toml"
