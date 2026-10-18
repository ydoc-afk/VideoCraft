"""Settings that used to be saved but ignored now reach the processors/UI."""

from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from videocraft.core import ffmpeg
from videocraft.core.config import AppConfig
from videocraft.core.job import Job
from videocraft.ui.panels.tools_panel import ToolsPanel


def teardown_function():
    ffmpeg.set_threads(0)


def test_with_threads_inserts_before_output():
    cmd = ["ffmpeg", "-i", "in.mp4", "out.mkv"]
    assert ffmpeg.with_threads(cmd) == cmd  # 0 = auto, untouched
    ffmpeg.set_threads(4)
    assert ffmpeg.with_threads(cmd) == ["ffmpeg", "-i", "in.mp4", "-threads", "4", "out.mkv"]


def test_converter_command_uses_configured_threads():
    from videocraft.processors.converter import ConverterProcessor
    ffmpeg.set_threads(2)
    job = Job(source_path=Path("/tmp/in.mp4"), output_path=Path("/tmp/out.mp4"), pipeline=["converter"])
    with patch("videocraft.core.nvenc.nvenc_encoder_for", return_value=None):
        cmd = ConverterProcessor()._build_command(job)
    assert cmd[-3:] == ["-threads", "2", "/tmp/out.mp4"]


def test_tools_panel_seeded_from_config():
    cfg = AppConfig.defaults()
    cfg.upscaler.default_scale = 2
    cfg.upscaler.default_model = "RealESRGAN_x4plus_anime"
    cfg.gpu.tile_size = 192
    cfg.colorizer.backend = "deoldify"
    cfg.colorizer.default_style = "stable"
    cfg.colorizer.saturation = 1.5
    cfg.hdr.peak_nits = 4000

    panel = ToolsPanel()
    panel.apply_config(cfg)

    up = panel.get_params("upscaler")
    assert up["scale"] == 2 and up["model"] == "RealESRGAN_x4plus_anime" and up["tile_size"] == 192
    col = panel.get_params("colorizer")
    assert (col["backend"], col["style"], col["saturation"]) == ("deoldify", "stable", 1.5)
    assert panel.get_params("hdr")["peak_nits"] == 4000

    cfg.gpu.tile_size = 0
    panel.apply_config(cfg)
    assert panel.get_params("upscaler")["tile_size"] == 0  # Auto


def test_removed_options_are_gone():
    panel = ToolsPanel()
    assert "noise_level" not in panel.get_params("denoiser")
    assert "remove_artifacts" not in panel.get_params("denoiser")
    assert "tonemap" not in panel.get_params("hdr")
    assert not hasattr(AppConfig.defaults().hdr, "tonemap")


def test_old_config_with_tonemap_still_loads(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[hdr]\npeak_nits = 600\ntonemap = "hable"\n')
    cfg = AppConfig.load(path)
    assert cfg.hdr.peak_nits == 600


def test_main_window_applies_runtime_settings():
    from videocraft.core.vram_manager import vram_manager
    from videocraft.ui.main_window import MainWindow

    win = MainWindow(ffmpeg_path=Path("ffmpeg"))
    old_device = vram_manager.device
    try:
        win.config.ffmpeg.threads = 3
        win.config.gpu.device = "cpu"
        win.config.general.concurrent_jobs = 2
        win._apply_runtime_settings()
        assert ffmpeg.with_threads(["a", "b"]) == ["a", "-threads", "3", "b"]
        assert vram_manager.device == "cpu"
        assert win.queue.concurrent_jobs == 2
    finally:
        vram_manager.device = old_device
