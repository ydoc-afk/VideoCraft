# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VideoCraft (onedir — feeds the AppImage build)."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# ── Bundle third-party package data (themes, fonts, resources) ──
qtm_datas, qtm_binaries, qtm_hidden = collect_all("qt_material")
qta_datas, qta_binaries, qta_hidden = collect_all("qtawesome")

# ── Bundle static FFmpeg + ffprobe if present in assets/bin/ ──
# (if absent, the app falls back to FFmpeg on PATH at runtime)
binaries = list(qtm_binaries) + list(qta_binaries)
_exe = ".exe" if sys.platform == "win32" else ""
for _tool in ("ffmpeg", "ffprobe"):
    _p = Path(f"assets/bin/{_tool}{_exe}")
    if _p.exists():
        binaries.append((str(_p), "assets/bin"))

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=[
        ("assets/themes", "assets/themes"),
    ] + qtm_datas + qta_datas,
    hiddenimports=[
        # App packages (collected explicitly — imported lazily in places)
        "processors",
        "processors.audio",
        "processors.converter",
        "processors.upscaler",
        "processors.denoiser",
        "processors.colorizer",
        "processors.hdr_converter",
        "processors.frame_processor",
        "processors.base_processor",
        "processors.audio.vocal_remover",
        "processors.audio.upmixer",
        "processors.archs",
        "processors.archs.scunet_arch",
        "ui.panels",
        "ui.panels.log_panel",
        "ui.panels.source_panel",
        "ui.panels.output_panel",
        "ui.panels.queue_panel",
        "ui.panels.tools_panel",
        "ui.dialogs",
        "ui.dialogs.preflight_dialog",
        "ui.dialogs.settings_dialog",
        "ui.dialogs.model_manager_dialog",
        "ui.widgets",
        "ui.widgets.drag_drop_area",
        "core.config",
        "core.ffmpeg",
        "core.theme",
        "core.job",
        "core.job_queue",
        "core.models_registry",
        "core.vram_manager",
        "core.worker",
        # Third-party (core runtime deps)
        "numpy",
        "PIL",
        "requests",
        "tomli_w",
        "qtawesome",
        "qt_material",
    ] + qtm_hidden + qta_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "tkinter",
        "unittest",
        # Heavy optional ML deps — kept out of the bundle; the app degrades
        # gracefully and users install them into their own environment.
        "torch",
        "torchvision",
        "basicsr",
        "realesrgan",
        "demucs",
        "matplotlib",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="videocraft",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VideoCraft",
)
