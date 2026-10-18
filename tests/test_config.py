"""Tests for core.config — TOML config load/save."""

import sys, os, tempfile, shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from videocraft.core.config import AppConfig


def test_default_config_values():
    """Fresh config has sensible defaults."""
    cfg = AppConfig.defaults()
    assert cfg.general.theme == "dark_amber.xml"
    assert cfg.general.concurrent_jobs == 1
    assert cfg.ffmpeg.path == "ffmpeg"
    assert cfg.ffmpeg.threads == 0
    assert cfg.gpu.device == "auto"
    assert cfg.gpu.tile_size == 0  # 0 = Auto (detect from VRAM)
    assert cfg.upscaler.default_scale == 4
    assert cfg.upscaler.default_model == "RealESRGAN_x4plus"
    assert cfg.colorizer.default_style == "artistic"
    assert cfg.colorizer.saturation == 1.0
    assert cfg.hdr.peak_nits == 1000


def test_save_and_load_roundtrip(tmp_path):
    """Save config to file, reload, verify all values match."""
    cfg = AppConfig.defaults()
    cfg.general.theme = "dark_blue.xml"
    cfg.general.concurrent_jobs = 2
    cfg.ffmpeg.path = "/usr/local/bin/ffmpeg"
    cfg.upscaler.default_scale = 2

    config_file = tmp_path / "config.toml"
    cfg.save(config_file)

    loaded = AppConfig.load(config_file)
    assert loaded.general.theme == "dark_blue.xml"
    assert loaded.general.concurrent_jobs == 2
    assert loaded.ffmpeg.path == "/usr/local/bin/ffmpeg"
    assert loaded.upscaler.default_scale == 2
    # Unchanged values retain defaults
    assert loaded.hdr.peak_nits == 1000


def test_save_escapes_special_characters(tmp_path):
    """Windows paths and quotes survive a save/load round-trip."""
    cfg = AppConfig.defaults()
    cfg.general.default_output_dir = r"C:\Users\test\Videos"
    cfg.ffmpeg.path = r'C:\tools\ff "custom"\ffmpeg.exe'

    config_file = tmp_path / "config.toml"
    cfg.save(config_file)

    loaded = AppConfig.load(config_file)
    assert loaded.general.default_output_dir == r"C:\Users\test\Videos"
    assert loaded.ffmpeg.path == r'C:\tools\ff "custom"\ffmpeg.exe'


def test_load_missing_file_returns_defaults(tmp_path):
    """Loading a nonexistent config file returns defaults."""
    config_file = tmp_path / "nonexistent.toml"
    cfg = AppConfig.load(config_file)
    assert cfg.general.theme == "dark_amber.xml"
    assert cfg.general.concurrent_jobs == 1


def test_old_config_with_colorizer_backend_still_loads(tmp_path):
    """Configs saved before DeOldify was dropped contain `backend`; they must still load."""
    path = tmp_path / "config.toml"
    path.write_text('[colorizer]\nbackend = "deoldify"\nsaturation = 1.4\n')
    cfg = AppConfig.load(path)
    assert cfg.colorizer.saturation == 1.4
    assert not hasattr(cfg.colorizer, "backend")
