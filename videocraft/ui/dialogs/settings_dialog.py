"""Settings dialog — app preferences persisted to TOML config."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QFileDialog,
    QGroupBox,
    QTabWidget,
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from videocraft.core.config import AppConfig
from videocraft.core.theme import available_themes

logger = logging.getLogger(__name__)

# Only themes qt-material actually ships (queried at import time).
_THEMES = available_themes()


class SettingsDialog(QDialog):
    """Application settings dialog.

    Tabs: General, FFmpeg, GPU, Tools.
    Changes are applied on Save and persisted to TOML.
    """

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumSize(550, 450)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # General tab
        self.tabs.addTab(self._build_general_tab(), "General")
        # FFmpeg tab
        self.tabs.addTab(self._build_ffmpeg_tab(), "FFmpeg")
        # GPU tab
        self.tabs.addTab(self._build_gpu_tab(), "GPU")
        # Tools tab
        self.tabs.addTab(self._build_tools_tab(), "Tools")

        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setMinimumWidth(80)
        btn_layout.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setMinimumWidth(80)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_defaults = QPushButton("Reset Defaults")
        self.btn_defaults.clicked.connect(self._on_defaults)
        btn_layout.addWidget(self.btn_defaults)

        layout.addLayout(btn_layout)

    def _build_general_tab(self) -> QGroupBox:
        group = QGroupBox()
        layout = QVBoxLayout(group)

        # Theme
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(_THEMES)
        theme_layout.addWidget(self.cmb_theme, 1)
        layout.addLayout(theme_layout)

        # Output directory
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Default output dir:"))
        self.le_output_dir = QLineEdit()
        self.le_output_dir.setPlaceholderText("Not set (uses source dir)")
        output_layout.addWidget(self.le_output_dir, 1)
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self._browse_output)
        output_layout.addWidget(self.btn_browse_output)
        layout.addLayout(output_layout)

        # Concurrent jobs
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("Concurrent jobs:"))
        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 8)
        concurrent_layout.addWidget(self.spin_concurrent)
        concurrent_layout.addStretch()
        layout.addLayout(concurrent_layout)

        # Hugging Face token (model downloads)
        hf_group = QGroupBox("Hugging Face (model downloads)")
        hf_layout = QHBoxLayout(hf_group)
        self.lbl_hf_status = QLabel("")
        hf_layout.addWidget(self.lbl_hf_status, 1)
        self.btn_hf_setup = QPushButton("Set up token…")
        self.btn_hf_setup.setToolTip("Step-by-step help to create and save a free access token")
        self.btn_hf_setup.clicked.connect(self._on_hf_setup)
        hf_layout.addWidget(self.btn_hf_setup)
        self.btn_hf_remove = QPushButton("Remove")
        self.btn_hf_remove.clicked.connect(self._on_hf_remove)
        hf_layout.addWidget(self.btn_hf_remove)
        layout.addWidget(hf_group)
        self._refresh_hf_status()

        layout.addStretch()
        return group

    def _refresh_hf_status(self) -> None:
        from videocraft.core import hf_auth

        saved = hf_auth.saved_token() is not None
        if hf_auth.get_token() and not saved:
            text = "Using the token from your HF_TOKEN environment variable."
        else:
            text = "Token saved on this computer." if saved else "No token set (usually not needed)."
        self.lbl_hf_status.setText(text)
        self.btn_hf_remove.setEnabled(saved)

    def _on_hf_setup(self) -> None:
        from videocraft.ui.dialogs.hf_token_dialog import HFTokenDialog

        HFTokenDialog(self).exec()
        self._refresh_hf_status()

    def _on_hf_remove(self) -> None:
        from videocraft.core import hf_auth

        hf_auth.save_token("")
        self._refresh_hf_status()

    def _build_ffmpeg_tab(self) -> QGroupBox:
        group = QGroupBox()
        layout = QVBoxLayout(group)

        # FFmpeg path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("FFmpeg path:"))
        self.le_ffmpeg_path = QLineEdit()
        self.le_ffmpeg_path.setPlaceholderText("ffmpeg (from PATH)")
        path_layout.addWidget(self.le_ffmpeg_path, 1)
        self.btn_browse_ffmpeg = QPushButton("Browse...")
        self.btn_browse_ffmpeg.clicked.connect(self._browse_ffmpeg)
        path_layout.addWidget(self.btn_browse_ffmpeg)
        layout.addLayout(path_layout)

        # Threads
        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel("Threads (0=auto):"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(0, 64)
        threads_layout.addWidget(self.spin_threads)
        threads_layout.addStretch()
        layout.addLayout(threads_layout)

        layout.addStretch()
        return group

    def _build_gpu_tab(self) -> QGroupBox:
        group = QGroupBox()
        layout = QVBoxLayout(group)

        # Device
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device:"))
        self.cmb_device = QComboBox()
        self.cmb_device.addItems(["auto", "cuda:0", "cpu"])
        device_layout.addWidget(self.cmb_device)
        device_layout.addStretch()
        layout.addLayout(device_layout)

        # Tile size — Auto (detect from VRAM) or a manual override
        self.chk_tile_auto = QCheckBox("Tile size: Auto (detect from VRAM)")
        self.chk_tile_auto.setToolTip(
            "Pick the upscaler tile size from the detected GPU's VRAM. "
            "Uncheck to set it manually."
        )
        self.chk_tile_auto.toggled.connect(
            lambda checked: self.spin_tile.setEnabled(not checked)
        )
        layout.addWidget(self.chk_tile_auto)

        tile_layout = QHBoxLayout()
        tile_layout.addWidget(QLabel("Manual tile size:"))
        self.spin_tile = QSpinBox()
        self.spin_tile.setRange(64, 1024)
        self.spin_tile.setSingleStep(32)
        tile_layout.addWidget(self.spin_tile)
        tile_layout.addStretch()
        layout.addLayout(tile_layout)

        # NVENC (NVIDIA hardware encoding)
        self.chk_nvenc = QCheckBox(
            "Use NVIDIA hardware encoding (NVENC) when available"
        )
        self.chk_nvenc.setToolTip(
            "Encode H.264/H.265/AV1 on the GPU when a supported NVIDIA card is "
            "detected. Falls back to software encoding automatically."
        )
        layout.addWidget(self.chk_nvenc)

        layout.addStretch()
        return group

    def _build_tools_tab(self) -> QGroupBox:
        group = QGroupBox()
        layout = QVBoxLayout(group)

        # Upscaler defaults
        upscaler_group = QGroupBox("Upscaler")
        upscaler_layout = QVBoxLayout()

        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Default scale:"))
        self.spin_scale = QSpinBox()
        self.spin_scale.setRange(2, 4)  # only 2x and 4x models exist
        self.spin_scale.setSingleStep(2)
        scale_layout.addWidget(self.spin_scale)
        scale_layout.addStretch()
        upscaler_layout.addLayout(scale_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Default model:"))
        self.cmb_upscaler_model = QComboBox()
        self.cmb_upscaler_model.addItems([
            "RealESRGAN_x4plus",
            "RealESRGAN_x4plus_anime",
        ])
        model_layout.addWidget(self.cmb_upscaler_model, 1)
        upscaler_layout.addLayout(model_layout)

        upscaler_group.setLayout(upscaler_layout)
        layout.addWidget(upscaler_group)

        # Colorizer defaults
        color_group = QGroupBox("Colorizer")
        color_layout = QVBoxLayout()

        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Default style:"))
        self.cmb_color_style = QComboBox()
        self.cmb_color_style.addItems(["artistic", "stable", "video"])
        style_layout.addWidget(self.cmb_color_style)
        style_layout.addStretch()
        color_layout.addLayout(style_layout)

        sat_layout = QHBoxLayout()
        sat_layout.addWidget(QLabel("Saturation:"))
        self.double_sat = QDoubleSpinBox()
        self.double_sat.setRange(0.0, 3.0)
        self.double_sat.setSingleStep(0.1)
        sat_layout.addWidget(self.double_sat)
        sat_layout.addStretch()
        color_layout.addLayout(sat_layout)

        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Backend:"))
        self.cmb_backend = QComboBox()
        self.cmb_backend.addItems(["ddcolor", "deoldify"])
        backend_layout.addWidget(self.cmb_backend)
        backend_layout.addStretch()
        color_layout.addLayout(backend_layout)

        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        # HDR defaults
        hdr_group = QGroupBox("HDR")
        hdr_layout = QVBoxLayout()

        nits_layout = QHBoxLayout()
        nits_layout.addWidget(QLabel("Peak nits:"))
        self.spin_nits = QSpinBox()
        self.spin_nits.setRange(100, 10000)
        self.spin_nits.setSingleStep(100)
        nits_layout.addWidget(self.spin_nits)
        nits_layout.addStretch()
        hdr_layout.addLayout(nits_layout)

        hdr_group.setLayout(hdr_layout)
        layout.addWidget(hdr_group)

        layout.addStretch()
        return group

    def _load_values(self) -> None:
        """Load current config values into UI controls."""
        cfg = self.config

        # General
        if cfg.general.theme in _THEMES:
            self.cmb_theme.setCurrentText(cfg.general.theme)
        self.le_output_dir.setText(cfg.general.default_output_dir)
        self.spin_concurrent.setValue(cfg.general.concurrent_jobs)

        # FFmpeg
        self.le_ffmpeg_path.setText(cfg.ffmpeg.path)
        self.spin_threads.setValue(cfg.ffmpeg.threads)

        # GPU
        self.cmb_device.setCurrentText(cfg.gpu.device)
        # tile_size 0 = Auto; show a sensible manual value when auto is on
        auto_tile = cfg.gpu.tile_size == 0
        self.chk_tile_auto.setChecked(auto_tile)
        self.spin_tile.setEnabled(not auto_tile)
        if auto_tile:
            from videocraft.core.vram_manager import vram_manager
            self.spin_tile.setValue(max(64, vram_manager.recommended_tile))
        else:
            self.spin_tile.setValue(cfg.gpu.tile_size)
        self.chk_nvenc.setChecked(cfg.gpu.use_nvenc)

        # Upscaler
        self.spin_scale.setValue(cfg.upscaler.default_scale)
        self.cmb_upscaler_model.setCurrentText(cfg.upscaler.default_model)

        # Colorizer
        self.cmb_color_style.setCurrentText(cfg.colorizer.default_style)
        self.double_sat.setValue(cfg.colorizer.saturation)
        self.cmb_backend.setCurrentText(cfg.colorizer.backend)

        # HDR
        self.spin_nits.setValue(cfg.hdr.peak_nits)

    def _save_values(self) -> None:
        """Save UI control values into config."""
        cfg = self.config

        # General
        cfg.general.theme = self.cmb_theme.currentText()
        cfg.general.default_output_dir = self.le_output_dir.text().strip()
        cfg.general.concurrent_jobs = self.spin_concurrent.value()

        # FFmpeg
        cfg.ffmpeg.path = self.le_ffmpeg_path.text().strip() or "ffmpeg"
        cfg.ffmpeg.threads = self.spin_threads.value()

        # GPU
        cfg.gpu.device = self.cmb_device.currentText()
        # 0 = Auto; otherwise the manual spinbox value
        cfg.gpu.tile_size = 0 if self.chk_tile_auto.isChecked() else self.spin_tile.value()
        cfg.gpu.use_nvenc = self.chk_nvenc.isChecked()
        # Apply immediately so the next job honors the new preference
        from videocraft.core.nvenc import set_nvenc_enabled
        set_nvenc_enabled(cfg.gpu.use_nvenc)

        # Upscaler
        cfg.upscaler.default_scale = self.spin_scale.value()
        cfg.upscaler.default_model = self.cmb_upscaler_model.currentText()

        # Colorizer
        cfg.colorizer.default_style = self.cmb_color_style.currentText()
        cfg.colorizer.saturation = self.double_sat.value()
        cfg.colorizer.backend = self.cmb_backend.currentText()

        # HDR
        cfg.hdr.peak_nits = self.spin_nits.value()

    def _on_save(self) -> None:
        """Save config and close dialog."""
        self._save_values()
        config_path = AppConfig.platform_config_path()
        try:
            self.config.save(config_path)
            logger.info("Settings saved to %s", config_path)
            self.accept()
        except OSError as e:
            QMessageBox.warning(self, "Save Error", f"Could not save settings:\n{e}")

    def _on_defaults(self) -> None:
        """Reset to default values."""
        reply = QMessageBox.question(
            self, "Reset Defaults",
            "Reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            new_cfg = AppConfig.defaults()
            # Replace values in-place so references stay valid
            for attr in ("general", "ffmpeg", "gpu", "upscaler", "colorizer", "hdr"):
                for k, v in vars(new_cfg.__getattribute__(attr)).items():
                    setattr(getattr(self.config, attr), k, v)
            self._load_values()

    def _browse_output(self) -> None:
        """Browse for output directory."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.le_output_dir.setText(folder)

    def _browse_ffmpeg(self) -> None:
        """Browse for FFmpeg binary."""
        path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Binary", "", "Executables (*)")
        if path:
            self.le_ffmpeg_path.setText(path)

    def get_theme(self) -> str:
        """Return the currently selected theme (for runtime switching)."""
        return self.cmb_theme.currentText()
