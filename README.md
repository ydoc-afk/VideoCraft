# VideoCraft — AI Video Enhancement Suite

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)

A cross-platform desktop application for AI-powered video and audio enhancement. Chain multiple tools together in a queue-based pipeline with real-time progress tracking, GPU-accelerated encoding, and automatic VRAM management.

<div align="center">

**Upscale** · **Denoise** · **Colorize** · **HDR Convert** · **Format Convert** · **Vocal Remove** · **Audio Upmix**

</div>

## Features

### AI Video Tools

| Tool | Description | Engine |
|------|-------------|--------|
| **Upscaler** | 2× or 4× super-resolution with Real-ESRGAN (general & anime models) | Real-ESRGAN |
| **Denoiser** | Remove noise and compression artifacts | SCUNet |
| **Colorizer** | Add color to black & white footage, preserving original luminance | DDColor / Deoldify |

### Video & Audio Tools

| Tool | Description | Engine |
|------|-------------|--------|
| **HDR Converter** | SDR → HDR10/HLG with proper BT.2020 metadata | FFmpeg zscale + tonemap |
| **Format Converter** | Convert between MP4, MKV, MOV, AVI, WebM, GIF and more | FFmpeg |
| **Vocal Remover** | Stem separation — isolate or remove vocals, drums, bass, other | Demucs |
| **Audio Upmixer** | Stereo → 5.1 or 7.1 surround sound | FFmpeg pan filter |

### Core Capabilities

- **Pipeline chaining** — run multiple tools in sequence (e.g. denoise → upscale → HDR)
- **NVENC hardware encoding** — automatic NVIDIA GPU encoding for H.264/H.265/AV1 with software fallback
- **Adaptive VRAM management** — auto-detects GPU memory and picks safe tile/batch sizes (GTX 1650 → RTX 5090)
- **Queue-based processing** — add multiple files, start/pause/cancel, real-time progress bars
- **Drag-and-drop** — drop files directly onto the window
- **Pre-flight checks** — validates FFmpeg, models, CUDA, and disk space before ML jobs
- **Model manager** — download, verify, and manage AI model weights from the UI
- **Themed UI** — 16+ dark and light themes via qt-material with runtime switching
- **Graceful cancellation** — kills FFmpeg/ML inference, cleans temp files, frees CUDA cache

## Installation

### Prerequisites

- **Python 3.11+**
- **FFmpeg** — install system-wide or place `ffmpeg` / `ffmpeg.exe` in `assets/bin/`
- **NVIDIA GPU** (optional but recommended for ML tools) — CUDA-capable GPU with PyTorch CUDA support

### Quick Start

```bash
# Clone the repository
git clone https://github.com/ydoc-afk/VideoCraft.git
cd VideoCraft

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install core dependencies (converter, HDR, upmixer work immediately)
pip install -r requirements.txt

# (Optional) Install ML dependencies for upscaler, denoiser, colorizer, vocal remover
pip install torch torchvision basicsr realesrgan opencv-python einops timm demucs

# Run the application
python main.py
```

### ML Dependencies by Tool

ML packages are **optional** — the app runs without them. Tools that need ML gracefully fall back to pass-through with a warning.

| Tool | Packages |
|------|----------|
| Upscaler | `torch`, `torchvision`, `basicsr`, `realesrgan`, `opencv-python` |
| Denoiser | `torch`, `einops`, `timm`, `opencv-python` |
| Colorizer | `torch`, `opencv-python` + DDColor or Deoldify inference packages |
| Vocal Remover | `demucs` (downloads its own weights on first run) |

## Usage

### Launching

```bash
python main.py
```

The app checks for FFmpeg on startup (bundled in `assets/bin/` first, then PATH). If not found, an error dialog is shown.

### Workflow

1. **Open files** — use File → Open, Open Folder, or drag-and-drop onto the window
2. **Select a tool** — choose from the Tools panel tabs (Upscaler, Denoiser, Colorizer, etc.)
3. **Configure settings** — adjust tool-specific parameters (scale factor, model, quality, etc.)
4. **Set output** — pick an output directory and format in the Output panel
5. **Add to queue** — selected files are added with the active tool's settings
6. **Start** — press F5 or click Start to begin processing

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open file(s) |
| `Ctrl+,` | Settings |
| `Ctrl+L` | Clear log |
| `Ctrl+Q` | Exit |
| `F5` | Start queue |
| `F6` | Pause queue |
| `Shift+F5` | Cancel selected jobs |

## Configuration

Settings are stored as TOML in a platform-specific directory:

| Platform | Path |
|----------|------|
| Linux | `~/.config/videocraftapp/config.toml` (or `$XDG_CONFIG_HOME/videocraftapp/`) |
| macOS | `~/Library/Application Support/VideoCraft/config.toml` |
| Windows | `%APPDATA%\VideoCraft\config.toml` |

### Config Sections

```toml
[general]
theme = "dark_amber.xml"
default_output_dir = ""
concurrent_jobs = 1

[ffmpeg]
path = "ffmpeg"          # custom path overrides auto-detection
threads = 0              # 0 = auto

[gpu]
device = "auto"          # auto | cuda:0 | cpu
tile_size = 0            # 0 = auto-detect from VRAM; >0 = manual override
use_nvenc = true         # prefer NVIDIA hardware encoding

[upscaler]
default_scale = 4
default_model = "RealESRGAN_x4plus"

[colorizer]
default_style = "artistic"
saturation = 1.0
backend = "ddcolor"      # ddcolor | deoldify

[hdr]
peak_nits = 1000
tonemap = "hable"
```

## VRAM Management

VideoCraft auto-detects your GPU and selects safe processing parameters:

| VRAM | Tier | Tile Size | Batch |
|------|------|-----------|-------|
| 32+ GB | Ultra | 1024 | 6 |
| 24 GB | High | 768 | 4 |
| 16 GB | High | 512 | 3 |
| 12 GB | Medium | 384 | 2 |
| 8 GB | Medium | 256 | 1 |
| 6 GB | Low | 192 | 1 |
| 4 GB | Low | 128 | 1 |
| < 4 GB | Minimal | 96 | 1 |

Set `tile_size = 0` in config (or leave the UI on "Auto") for automatic selection. Manual values are clamped to the safe maximum for your card.

## AI Models

Models are managed through the **Model Manager** (Tools → Model Manager). Weights are stored in `models/` and downloaded automatically when needed.

### Available Models

| Model | Tool | Size | Source |
|-------|------|------|--------|
| RealESRGAN x4plus | Upscaler (4× general) | 64 MB | Real-ESRGAN |
| RealESRGAN x2plus | Upscaler (2× general) | 64 MB | Real-ESRGAN |
| RealESRGAN x4plus Anime | Upscaler (4× anime) | 18 MB | Real-ESRGAN |
| SCUNet (Color, real noise) | Denoiser | 69 MB | KAIR |
| SCUNet (Color, Gaussian σ25) | Denoiser | 69 MB | KAIR |
| DDColor (Artistic) | Colorizer | 875 MB | HuggingFace |
| DDColor (ModelScope) | Colorizer | 875 MB | HuggingFace |
| Deoldify (Artistic) | Colorizer | 243 MB | DeepAI |
| Deoldify (Stable) | Colorizer | 834 MB | HuggingFace |
| Deoldify (Video) | Colorizer | 243 MB | DeepAI |

Demucs (vocal remover) downloads its own weights automatically on first run.

## Architecture

```
VideoCraft
├── main.py                  # Entry point: FFmpeg check, theme, window
├── core/
│   ├── config.py            # TOML config (platform-specific paths)
│   ├── ffmpeg.py            # FFmpeg/ffprobe binary resolution
│   ├── job.py               # Job dataclass (pipeline, params, status)
│   ├── job_queue.py         # Thread-safe queue with ML concurrency limits
│   ├── models_registry.py   # Model metadata, download, verification
│   ├── nvenc.py             # NVENC detection and encoder selection
│   ├── theme.py             # qt-material theme + custom QSS
│   ├── vram_manager.py      # CUDA VRAM detection and tile sizing
│   └── worker.py            # QThread worker with multi-step pipelines
├── processors/
│   ├── base_processor.py    # Abstract base (process() → log generator)
│   ├── converter.py         # FFmpeg format conversion
│   ├── frame_processor.py   # Frame extraction/inference/re-encode base
│   ├── upscaler.py          # Real-ESRGAN upscaling
│   ├── denoiser.py          # SCUNet denoising
│   ├── colorizer.py         # DDColor / Deoldify colorization
│   ├── hdr_converter.py     # SDR → HDR10/HLG
│   ├── archs/               # Vendored model architectures (SCUNet)
│   └── audio/
│       ├── vocal_remover.py # Demucs stem separation
│       └── upmixer.py       # Stereo → 5.1/7.1 upmix
├── ui/
│   ├── main_window.py       # QMainWindow with splitter layout
│   ├── panels/
│   │   ├── source_panel.py  # File picker with ffprobe metadata
│   │   ├── output_panel.py  # Output dir, format, codec, quality
│   │   ├── tools_panel.py   # Tabbed tool settings
│   │   ├── queue_panel.py   # Job table with progress bars
│   │   └── log_panel.py     # Color-coded log output
│   ├── dialogs/
│   │   ├── settings_dialog.py      # App settings
│   │   ├── model_manager_dialog.py # Model download manager
│   │   └── preflight_dialog.py     # Pre-flight validation
│   └── widgets/
│       └── drag_drop_area.py       # Drag-and-drop support
├── assets/
│   ├── bin/                 # Bundled FFmpeg binaries
│   ├── icons/               # Application icons
│   └── themes/              # Custom QSS overrides
└── models/                  # AI model weights (downloaded at runtime)
```

### Key Design Decisions

- **ML models are lazy-loaded** — never at import time; loaded inside `process()` on first use
- **Single concurrent ML job** — hard limit enforced by the job queue to prevent OOM
- **FFmpeg via `subprocess.Popen`** — never `os.system()`; all calls wrapped with timeout and cancellation
- **Frame processors share a common base** — `FrameProcessor` handles extraction, re-encoding, temp cleanup, and VRAM cache management
- **NVENC is probed at runtime** — a throwaway encode to `null` verifies each encoder actually works on the hardware
- **Graceful degradation** — missing ML deps fall back to pass-through; missing NVENC falls back to software encoding

## Development

### Running Tests

```bash
pip install pytest
pytest tests/ -v
```

### Project Structure for Contributors

- **`core/`** — shared infrastructure (config, queue, FFmpeg, GPU detection)
- **`processors/`** — tool implementations; each inherits `BaseProcessor` or `FrameProcessor`
- **`ui/`** — PyQt6 panels, dialogs, and widgets
- **`tests/`** — unit tests for core components and processors

### Adding a New Processor

1. Create a class inheriting `BaseProcessor` (for direct FFmpeg tools) or `FrameProcessor` (for frame-based ML tools)
2. Implement `process(self, job)` yielding log line strings
3. Register it in `core/worker.py` under `_PROCESSORS`
4. Add a settings tab in `ui/panels/tools_panel.py`

## License

MIT

## Acknowledgments

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — video upscaling
- [SCUNet / KAIR](https://github.com/cszn/KAIR) — video denoising
- [DDColor](https://github.com/piddnad/DDColor) — colorization
- [Deoldify](https://github.com/jantic/Deoldify) — colorization
- [Demucs](https://github.com/facebookresearch/demucs) — stem separation
- [FFmpeg](https://ffmpeg.org/) — video/audio processing
- [qt-material](https://github.com/UN-GCPDS/qt-material) — theming
- [qtawesome](https://github.com/pyqt/qtawesome) — icons
