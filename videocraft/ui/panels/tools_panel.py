"""Tools panel — tab widget with settings UI for each AI tool."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QSlider,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from PyQt6.QtCore import Qt

from videocraft.core.theme import mark_hint


class ToolsPanel(QFrame):
    """Tab widget wiring all tools' settings UIs.

    Tabs: Upscaler, Denoiser, Colorizer, HDR, Audio, Convert.
    Each tab shows tool-specific settings that map to job params.
    The active tab selects which tool new jobs will run.
    """

    # Tab index → tool name ("audio" resolves via the mode radio buttons)
    _TAB_TOOLS = ["upscaler", "denoiser", "colorizer", "hdr", "audio", "converter"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._params: dict[str, dict] = {
            "upscaler": {},
            "denoiser": {},
            "colorizer": {},
            "hdr": {},
            "audio": {},
            "converter": {},
        }
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()

        # Upscaler tab
        self.tab_widget.addTab(self._make_tab(self._build_upscaler_tab()), "Upscaler")
        # Denoiser tab
        self.tab_widget.addTab(self._make_tab(self._build_denoiser_tab()), "Denoiser")
        # Colorizer tab
        self.tab_widget.addTab(self._make_tab(self._build_colorizer_tab()), "Colorizer")
        # HDR tab
        self.tab_widget.addTab(self._make_tab(self._build_hdr_tab()), "HDR")
        # Audio tab
        self.tab_widget.addTab(self._make_tab(self._build_audio_tab()), "Audio")
        # Convert tab
        self.tab_widget.addTab(self._make_tab(self._build_convert_tab()), "Convert")

        layout.addWidget(self.tab_widget)

    def _make_tab(self, frame: QFrame) -> QScrollArea:
        """Left-align each control row, then wrap the tab in a scroll area.

        The scroll area guarantees the tool controls are never clipped when
        the splitter gives the panel less than its preferred height (three
        group boxes need ~300px; a short panel would otherwise squeeze the
        boxes below their minimum and cut off the radios/combos).
        """
        self._left_align_rows(frame)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(frame)
        return scroll

    @staticmethod
    def _left_align_rows(frame: QWidget) -> None:
        """Make control rows sit at their natural width on the left instead
        of splitting the row evenly.

        Combos/spinboxes/radios default to expandable size policies, so a
        trailing stretch alone isn't enough — the layout still hands them
        slack inconsistently. We hard-cap each input to its natural width
        (a constraint the layout cannot violate), then a trailing stretch
        absorbs the remaining space. Rows with a slider are left alone —
        sliders should fill the row."""
        inputs = (QComboBox, QSpinBox, QDoubleSpinBox, QRadioButton, QCheckBox)
        pad = {QComboBox: 34, QSpinBox: 24, QDoubleSpinBox: 24}
        for hbox in frame.findChildren(QHBoxLayout):
            widgets = [hbox.itemAt(i).widget() for i in range(hbox.count())]
            if any(isinstance(w, QSlider) for w in widgets):
                continue
            for w in widgets:
                if isinstance(w, inputs):
                    hint = w.sizeHint().width()
                    if hint > 0:
                        w.setMaximumWidth(hint + pad.get(type(w), 4))
            last = hbox.itemAt(hbox.count() - 1) if hbox.count() else None
            if last is None or last.spacerItem() is None:
                hbox.addStretch()

    # ── Upscaler Tab ──

    def _build_upscaler_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Scale factor
        scale_group = QGroupBox("Scale Factor")
        scale_layout = QHBoxLayout()
        self.upscaler_scale_group = QButtonGroup()
        rb_2x = QRadioButton("2x")
        rb_4x = QRadioButton("4x")
        rb_4x.setChecked(True)
        self.upscaler_scale_group.addButton(rb_2x, 2)
        self.upscaler_scale_group.addButton(rb_4x, 4)
        scale_layout.addWidget(rb_2x)
        scale_layout.addWidget(rb_4x)
        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)

        # Model selector
        model_group = QGroupBox("Model")
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.upscaler_model = QComboBox()
        self.upscaler_model.addItems([
            "RealESRGAN_x4plus (General)",
            "RealESRGAN_x4plus_anime (Animation)",
        ])
        model_layout.addWidget(self.upscaler_model)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Tile size — Auto (detect from VRAM) by default, with manual override
        from videocraft.core.vram_manager import vram_manager

        tile_group = QGroupBox("Tile Size")
        tile_outer = QVBoxLayout()

        self.upscaler_tile_auto = QCheckBox("Auto (detect from VRAM)")
        self.upscaler_tile_auto.setChecked(True)
        self.upscaler_tile_auto.toggled.connect(self._on_tile_auto_toggled)
        tile_outer.addWidget(self.upscaler_tile_auto)

        self.upscaler_tile_info = QLabel(f"Detected: {vram_manager.summary()}")
        self.upscaler_tile_info.setStyleSheet("font-size: 11px;")
        mark_hint(self.upscaler_tile_info, True)
        tile_outer.addWidget(self.upscaler_tile_info)

        tile_layout = QHBoxLayout()
        tile_layout.addWidget(QLabel("Tile:"))
        self.upscaler_tile = QSpinBox()
        self.upscaler_tile.setRange(96, 1024)
        # Seed the manual value with the auto recommendation as a sane start
        self.upscaler_tile.setValue(max(96, vram_manager.recommended_tile))
        self.upscaler_tile.setSingleStep(32)
        self.upscaler_tile.setEnabled(False)  # disabled while Auto is on
        tile_layout.addWidget(self.upscaler_tile)
        tile_outer.addLayout(tile_layout)

        tile_group.setLayout(tile_outer)
        layout.addWidget(tile_group)

        layout.addStretch()
        return frame

    # ── Denoiser Tab ──

    def _build_denoiser_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Model
        model_group = QGroupBox("Model")
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.denoiser_model = QComboBox()
        self.denoiser_model.addItems([
            "SCUNet (Real-world noise)",
            "SCUNet (Gaussian noise)",
        ])
        model_layout.addWidget(self.denoiser_model)
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        layout.addStretch()
        return frame

    # ── Colorizer Tab ──

    def _build_colorizer_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Backend
        backend_group = QGroupBox("Backend")
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Model:"))
        self.colorizer_backend = QComboBox()
        self.colorizer_backend.addItems([
            "DDColor (Artistic)",
            "DDColor (ModelScope)",
        ])
        backend_layout.addWidget(self.colorizer_backend)
        backend_group.setLayout(backend_layout)
        layout.addWidget(backend_group)

        # Saturation
        sat_group = QGroupBox("Saturation")
        sat_layout = QHBoxLayout()
        sat_layout.addWidget(QLabel("Saturation:"))
        self.colorizer_saturation = QDoubleSpinBox()
        self.colorizer_saturation.setRange(0.0, 3.0)
        self.colorizer_saturation.setValue(1.0)
        self.colorizer_saturation.setSingleStep(0.1)
        sat_layout.addWidget(self.colorizer_saturation)
        sat_group.setLayout(sat_layout)
        layout.addWidget(sat_group)

        layout.addStretch()
        return frame

    # ── HDR Tab ──

    def _build_hdr_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Target format
        fmt_group = QGroupBox("Target Format")
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Format:"))
        self.hdr_format = QComboBox()
        self.hdr_format.addItems(["HDR10", "HLG"])
        fmt_layout.addWidget(self.hdr_format)
        fmt_group.setLayout(fmt_layout)
        layout.addWidget(fmt_group)

        # Peak brightness
        peak_group = QGroupBox("Peak Brightness")
        peak_layout = QHBoxLayout()
        peak_layout.addWidget(QLabel("Peak nits:"))
        self.hdr_peak_nits = QSpinBox()
        self.hdr_peak_nits.setRange(100, 10000)
        self.hdr_peak_nits.setValue(1000)
        self.hdr_peak_nits.setSingleStep(100)
        peak_layout.addWidget(self.hdr_peak_nits)
        peak_group.setLayout(peak_layout)
        layout.addWidget(peak_group)

        layout.addStretch()
        return frame

    # ── Audio Tab ──

    def _build_audio_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Mode selector
        mode_group = QGroupBox("Mode")
        mode_layout = QHBoxLayout()
        self.audio_mode_group = QButtonGroup()
        rb_vocal = QRadioButton("Vocal Remover")
        rb_upmix = QRadioButton("Audio Upmixer")
        rb_vocal.setChecked(True)
        self.audio_mode_group.addButton(rb_vocal, 0)
        self.audio_mode_group.addButton(rb_upmix, 1)
        mode_layout.addWidget(rb_vocal)
        mode_layout.addWidget(rb_upmix)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Vocal remover settings
        vr_group = QGroupBox("Vocal Remover Settings")
        vr_layout = QVBoxLayout()

        # Stem checkboxes
        stem_layout = QHBoxLayout()
        stem_layout.addWidget(QLabel("Keep stems:"))
        self.audio_stem_vocals = QCheckBox("Vocals")
        self.audio_stem_vocals.setChecked(True)
        self.audio_stem_drums = QCheckBox("Drums")
        self.audio_stem_bass = QCheckBox("Bass")
        self.audio_stem_other = QCheckBox("Other")
        stem_layout.addWidget(self.audio_stem_vocals)
        stem_layout.addWidget(self.audio_stem_drums)
        stem_layout.addWidget(self.audio_stem_bass)
        stem_layout.addWidget(self.audio_stem_other)
        vr_layout.addLayout(stem_layout)

        # Quick mode — on by default: a "vocal remover" should remove
        # vocals out of the box, not keep only them.
        self.audio_quick_mode = QCheckBox("Quick mode: Remove Vocals (keep everything else)")
        self.audio_quick_mode.toggled.connect(self._on_vocal_quick_mode)
        self.audio_quick_mode.setChecked(True)
        vr_layout.addWidget(self.audio_quick_mode)

        # Output format
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Output format:"))
        self.audio_output_format = QComboBox()
        self.audio_output_format.addItems(["WAV", "FLAC", "AAC"])
        fmt_layout.addWidget(self.audio_output_format)
        vr_layout.addLayout(fmt_layout)

        vr_group.setLayout(vr_layout)
        layout.addWidget(vr_group)

        # Upmixer settings
        upmix_group = QGroupBox("Upmixer Settings")
        upmix_layout = QVBoxLayout()

        # Target layout
        tl_layout = QHBoxLayout()
        tl_layout.addWidget(QLabel("Target layout:"))
        self.audio_channel_layout = QComboBox()
        self.audio_channel_layout.addItems(["5.1 Surround", "7.1 Surround"])
        tl_layout.addWidget(self.audio_channel_layout)
        upmix_layout.addLayout(tl_layout)

        # Bitrate
        br_layout = QHBoxLayout()
        br_layout.addWidget(QLabel("Bitrate:"))
        self.audio_bitrate = QComboBox()
        self.audio_bitrate.addItems(["384k", "640k", "1024k"])
        br_layout.addWidget(self.audio_bitrate)
        upmix_layout.addLayout(br_layout)

        # LFE gain
        lfe_layout = QHBoxLayout()
        lfe_layout.addWidget(QLabel("LFE gain (dB):"))
        self.audio_lfe_gain = QDoubleSpinBox()
        self.audio_lfe_gain.setRange(-12.0, 12.0)
        self.audio_lfe_gain.setValue(0.0)
        self.audio_lfe_gain.setSingleStep(1.0)
        lfe_layout.addWidget(self.audio_lfe_gain)
        upmix_layout.addLayout(lfe_layout)

        upmix_group.setLayout(upmix_layout)
        layout.addWidget(upmix_group)

        layout.addStretch()
        return frame

    def _on_vocal_quick_mode(self, checked: bool) -> None:
        """Toggle stem checkboxes when quick mode is enabled."""
        if checked:
            # Remove vocals = keep everything except vocals
            self.audio_stem_vocals.setChecked(False)
            self.audio_stem_drums.setChecked(True)
            self.audio_stem_bass.setChecked(True)
            self.audio_stem_other.setChecked(True)
        else:
            self.audio_stem_vocals.setChecked(True)

    # ── Convert Tab ──

    def _build_convert_tab(self) -> QFrame:
        frame = QFrame()
        layout = QVBoxLayout(frame)

        # Container
        container_group = QGroupBox("Container")
        container_layout = QHBoxLayout()
        container_layout.addWidget(QLabel("Format:"))
        self.convert_container = QComboBox()
        self.convert_container.addItems(["MP4", "MKV", "MOV", "AVI", "WebM", "GIF"])
        container_layout.addWidget(self.convert_container)
        container_group.setLayout(container_layout)
        layout.addWidget(container_group)

        # Video codec
        vc_group = QGroupBox("Video Codec")
        vc_layout = QHBoxLayout()
        vc_layout.addWidget(QLabel("Codec:"))
        self.convert_video_codec = QComboBox()
        self.convert_video_codec.addItems(["H.264", "H.265", "AV1", "VP9", "Copy"])
        vc_layout.addWidget(self.convert_video_codec)
        vc_group.setLayout(vc_layout)
        layout.addWidget(vc_group)

        # Audio codec
        ac_group = QGroupBox("Audio Codec")
        ac_layout = QHBoxLayout()
        ac_layout.addWidget(QLabel("Codec:"))
        self.convert_audio_codec = QComboBox()
        self.convert_audio_codec.addItems(["AAC", "MP3", "FLAC", "Copy", "None"])
        ac_layout.addWidget(self.convert_audio_codec)
        ac_group.setLayout(ac_layout)
        layout.addWidget(ac_group)

        # CRF
        crf_group = QGroupBox("Quality (CRF)")
        crf_layout = QHBoxLayout()
        crf_layout.addWidget(QLabel("CRF:"))
        self.convert_crf = QSlider(Qt.Orientation.Horizontal)
        self.convert_crf.setRange(0, 51)
        self.convert_crf.setValue(23)
        self.convert_crf.setTickPosition(QSlider.TickPosition.TicksBelow)
        crf_layout.addWidget(self.convert_crf)
        self.convert_crf_label = QLabel("23")
        self.convert_crf_label.setFixedWidth(30)
        crf_layout.addWidget(self.convert_crf_label)
        self.convert_crf.valueChanged.connect(
            lambda v: self.convert_crf_label.setText(str(v))
        )
        crf_outer = QVBoxLayout()
        crf_outer.addLayout(crf_layout)

        # Preset buttons (mutually exclusive via QButtonGroup)
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        self._crf_presets: dict[str, QPushButton] = {}
        for name, crf in (("Fast", 28), ("Balanced", 23), ("Quality", 18)):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(crf == 23)
            btn.clicked.connect(lambda _=False, c=crf: self._set_crf_preset(c))
            self._preset_group.addButton(btn)
            self._crf_presets[name] = btn
            preset_layout.addWidget(btn)
        crf_outer.addLayout(preset_layout)
        crf_group.setLayout(crf_outer)
        layout.addWidget(crf_group)
        self.convert_crf.valueChanged.connect(self._on_convert_crf_changed)

        layout.addStretch()
        return frame

    def _on_convert_crf_changed(self, value: int) -> None:
        """Uncheck the presets on *manual* CRF adjustment only — preset
        clicks also move the slider and must not uncheck themselves."""
        if getattr(self, "_applying_preset", False):
            return
        # An exclusive QButtonGroup ignores programmatic unchecks, so lift
        # exclusivity for a moment to reach the "no preset" state.
        self._preset_group.setExclusive(False)
        for btn in self._crf_presets.values():
            btn.setChecked(False)
        self._preset_group.setExclusive(True)

    def _set_crf_preset(self, crf: int) -> None:
        """Set the CRF slider from a preset button."""
        self._applying_preset = True
        try:
            self.convert_crf.setValue(crf)
        finally:
            self._applying_preset = False

    # ── Params Collection ──

    def current_tool(self) -> str:
        """Return the tool name for the currently active tab."""
        tool = self._TAB_TOOLS[self.tab_widget.currentIndex()]
        if tool == "audio":
            return "vocal_remover" if self.audio_mode_group.checkedId() == 0 else "upmixer"
        return tool

    def get_params(self, tool_name: str) -> dict:
        """Get params dict for a specific tool from the current tab settings."""
        if tool_name == "upscaler":
            return self._get_upscaler_params()
        elif tool_name == "denoiser":
            return self._get_denoiser_params()
        elif tool_name == "colorizer":
            return self._get_colorizer_params()
        elif tool_name == "hdr":
            return self._get_hdr_params()
        elif tool_name in ("vocal_remover", "upmixer"):
            return self._get_audio_params(tool_name)
        elif tool_name == "converter":
            return self._get_converter_params()
        return {}

    def apply_config(self, config) -> None:
        """Seed the tool controls from the saved defaults in Settings."""
        from videocraft.processors.upscaler import UpscalerProcessor

        # Upscaler: scale, model, tile (gpu.tile_size 0 = Auto)
        scale = UpscalerProcessor.get_scale_factor({"scale": config.upscaler.default_scale})
        button = self.upscaler_scale_group.button(scale)
        if button is not None:
            button.setChecked(True)
        want_anime = "anime" in config.upscaler.default_model.lower()
        self.upscaler_model.setCurrentIndex(1 if want_anime else 0)
        tile = config.gpu.tile_size
        self.upscaler_tile_auto.setChecked(tile <= 0)
        if tile > 0:
            self.upscaler_tile.setValue(max(self.upscaler_tile.minimum(), tile))

        # Colorizer: style → combo entry, saturation
        style_entries = {"artistic": "DDColor (Artistic)", "stable": "DDColor (ModelScope)"}
        self.colorizer_backend.setCurrentText(
            style_entries.get(config.colorizer.default_style, "DDColor (Artistic)")
        )
        self.colorizer_saturation.setValue(config.colorizer.saturation)

        # HDR
        self.hdr_peak_nits.setValue(config.hdr.peak_nits)

    def _on_tile_auto_toggled(self, checked: bool) -> None:
        """Enable the manual tile spinbox only when Auto is unchecked."""
        self.upscaler_tile.setEnabled(not checked)

    def _get_upscaler_params(self) -> dict:
        scale_map = {
            "RealESRGAN_x4plus (General)": "RealESRGAN_x4plus",
            "RealESRGAN_x4plus_anime (Animation)": "RealESRGAN_x4plus_anime",
        }
        # tile_size=0 tells the upscaler to auto-pick from detected VRAM
        tile_size = 0 if self.upscaler_tile_auto.isChecked() else self.upscaler_tile.value()
        return {
            "scale": self.upscaler_scale_group.checkedId(),
            "model": scale_map.get(self.upscaler_model.currentText(), "RealESRGAN_x4plus"),
            "tile_size": tile_size,
        }

    def _get_denoiser_params(self) -> dict:
        # Values are model-registry keys (core/models_registry.py)
        model_map = {
            "SCUNet (Real-world noise)": "scunet-color-real",
            "SCUNet (Gaussian noise)": "scunet-color-gaussian",
        }
        return {
            "model": model_map.get(self.denoiser_model.currentText(), "scunet-color-real"),
        }

    def _get_colorizer_params(self) -> dict:
        # ColorizerProcessor expects backend ("ddcolor") and
        # style ("artistic" | "stable" | "video") as separate params.
        backend_map = {
            "DDColor (Artistic)": ("ddcolor", "artistic"),
            "DDColor (ModelScope)": ("ddcolor", "stable"),
        }
        backend, style = backend_map.get(
            self.colorizer_backend.currentText(), ("ddcolor", "artistic")
        )
        return {
            "backend": backend,
            "style": style,
            "saturation": self.colorizer_saturation.value(),
        }

    def _get_hdr_params(self) -> dict:
        return {
            "hdr_format": "hdr10" if self.hdr_format.currentText() == "HDR10" else "hlg",
            "peak_nits": self.hdr_peak_nits.value(),
        }

    def _get_audio_params(self, tool_name: str) -> dict:
        if tool_name == "vocal_remover":
            stems = []
            if self.audio_stem_vocals.isChecked():
                stems.append("vocals")
            if self.audio_stem_drums.isChecked():
                stems.append("drums")
            if self.audio_stem_bass.isChecked():
                stems.append("bass")
            if self.audio_stem_other.isChecked():
                stems.append("other")

            fmt_map = {"WAV": "wav", "FLAC": "flac", "AAC": "aac"}
            return {
                "stems": stems,
                "output_format": fmt_map.get(self.audio_output_format.currentText(), "wav"),
                "mode": "remove_vocals" if self.audio_quick_mode.isChecked() else "full_separation",
            }
        else:
            layout_map = {"5.1 Surround": "5.1", "7.1 Surround": "7.1"}
            return {
                "channel_layout": layout_map.get(self.audio_channel_layout.currentText(), "5.1"),
                "bitrate": self.audio_bitrate.currentText(),
                "lfe_gain": self.audio_lfe_gain.value(),
            }

    def _get_converter_params(self) -> dict:
        container_map = {
            "MP4": "mp4", "MKV": "mkv", "MOV": "mov",
            "AVI": "avi", "WebM": "webm", "GIF": "gif",
        }
        video_map = {
            "H.264": "h264", "H.265": "h265", "AV1": "av1",
            "VP9": "vp9", "Copy": "copy",
        }
        audio_map = {
            "AAC": "aac", "MP3": "mp3", "FLAC": "flac",
            "Copy": "copy", "None": "none",
        }
        return {
            "container": container_map.get(self.convert_container.currentText(), "mp4"),
            "video_codec": video_map.get(self.convert_video_codec.currentText(), "h264"),
            "audio_codec": audio_map.get(self.convert_audio_codec.currentText(), "aac"),
            "crf": self.convert_crf.value(),
        }

    def get_all_params(self) -> dict[str, dict]:
        """Get params for all tools at once."""
        return {
            "upscaler": self._get_upscaler_params(),
            "denoiser": self._get_denoiser_params(),
            "colorizer": self._get_colorizer_params(),
            "hdr": self._get_hdr_params(),
            "vocal_remover": self._get_audio_params("vocal_remover"),
            "upmixer": self._get_audio_params("upmixer"),
            "converter": self._get_converter_params(),
        }
