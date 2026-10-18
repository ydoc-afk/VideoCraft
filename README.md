# VideoCraft — AI Video Enhancement Suite

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![CI](https://github.com/ydoc-afk/VideoCraft/actions/workflows/ci.yml/badge.svg)](https://github.com/ydoc-afk/VideoCraft/actions/workflows/ci.yml)

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
| **Colorizer** | Add color to black & white footage, preserving original luminance | DDColor |

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

## Status

VideoCraft is **early software (0.x)** — expect rough edges, and please report
what you find in the [issue tracker](https://github.com/ydoc-afk/VideoCraft/issues).

- **Working today:** Format Converter, HDR Converter and Audio Upmixer (pure FFmpeg).
- **Needs optional ML packages and a GPU for good speed:** Upscaler, Denoiser and Vocal Remover.
  If the packages are missing, these tools **copy the input through unchanged** and log a
  warning — check the log if the output looks identical to the input.
- **Colorizer uses DDColor** (inference code vendored from the upstream project). It colorizes each
  frame on its own, so expect some colour flicker on moving footage; it has not been tested with real
  weights on a GPU yet.
- Linux only for now; AMD GPUs (ROCm) are untested.

See [CHANGELOG.md](CHANGELOG.md) for what changed between versions.

## Installation

VideoCraft currently targets **Linux** (a Windows installer is planned). The AI tools run best on an
**NVIDIA GPU**; everything also works on CPU, just slowly.

### Prerequisites

- **Python 3.11 or 3.12** (3.13 is not supported for the AI tools yet — the Real-ESRGAN dependency `basicsr` does not build on it)
- **FFmpeg** — e.g. `sudo apt install ffmpeg`
- **NVIDIA driver** (optional but recommended) — nothing else to install; PyTorch brings its own CUDA runtime

### Quick install

```bash
git clone https://github.com/ydoc-afk/VideoCraft.git
cd VideoCraft
./install.sh
```

`install.sh` creates a private environment, installs VideoCraft, detects your NVIDIA driver, and
installs the matching PyTorch build and the other AI packages (this downloads several GB). It adds
a `videocraft` command and an app-menu entry, then runs a self-check and tells you which tools work.

| Option | Effect |
|--------|--------|
| `./install.sh --gpu cpu` | force the CPU build of PyTorch (or `--gpu nvidia`) |
| `./install.sh --no-ml` | install the app only; add the AI tools later with `videocraft setup` |
| `./install.sh --torch-index-url URL` | install PyTorch from another index, e.g. an AMD ROCm build (untested) |
| `./install.sh --uninstall` | remove the app (your config and downloaded models are kept) |

To update, `git pull` and run `./install.sh` again.

### Install with pipx

```bash
pipx install "git+https://github.com/ydoc-afk/VideoCraft.git"
videocraft setup          # installs PyTorch + the AI packages into the same environment
```

### What `videocraft setup` installs

AI packages are **optional** — the converter, HDR converter and audio upmixer work without them.
Tools that need ML fall back to pass-through with a warning if they are missing.

| Tool | Packages |
|------|----------|
| Upscaler | `torch`, `torchvision`, `basicsr`, `realesrgan`, `opencv-python` |
| Denoiser | `torch`, `einops`, `timm`, `opencv-python` |
| Colorizer | `torch`, `opencv-python` (the DDColor code is built in) |
| Vocal Remover | `demucs` (downloads its own weights on first run) |

`videocraft setup --gpu auto|nvidia|cpu` can be re-run at any time; `--dry-run` shows what it would install.

### From source (development)

```bash
git clone https://github.com/ydoc-afk/VideoCraft.git && cd VideoCraft
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
videocraft setup          # optional: AI tools
python -m videocraft      # or: videocraft
```

## Usage

### Launching

```bash
videocraft
```

The app checks for FFmpeg on startup (on your PATH, or the path set in Settings → FFmpeg). If not found, an error dialog is shown.

### Workflow

1. **Open files** — use File → Open, Open Folder, or drag-and-drop onto the window
2. **Select a tool** — choose from the Tools panel tabs (Upscaler, Denoiser, Colorizer, etc.)
3. **Configure settings** — adjust tool-specific parameters (scale factor, model, quality, etc.)
4. **Set output** — pick the destination folder in the Output panel (format, codec and quality for conversions live on the **Convert** tab)
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

[hdr]
peak_nits = 1000
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

Models are managed through the **Model Manager** (Tools → Model Manager). Weights are stored in your user data folder (`~/.local/share/videocraft/models` on Linux) and downloaded automatically when needed.

### Available Models

| Model | Tool | Size | Source |
|-------|------|------|--------|
| RealESRGAN x4plus | Upscaler (4× general) | 64 MB | Real-ESRGAN |
| RealESRGAN x2plus | Upscaler (2× general) | 64 MB | Real-ESRGAN |
| RealESRGAN x4plus Anime | Upscaler (4× anime) | 18 MB | Real-ESRGAN |
| SCUNet (Color, real noise) | Denoiser | 69 MB | KAIR |
| SCUNet (Color, Gaussian σ25) | Denoiser | 69 MB | KAIR |
| DDColor (Artistic) | Colorizer | 870 MB | HuggingFace |
| DDColor (ModelScope) | Colorizer | 870 MB | HuggingFace |

Demucs (vocal remover) downloads its own weights automatically on first run.

Every model above has its SHA-256 pinned in the app: a download that doesn't match is discarded with a clear message, and **Verify Installed** in the Model Manager re-checks the files you already have (hover a status to see its hash). If an upstream author re-uploads a model, run the **Model hashes** workflow (or `python scripts/compute_model_hashes.py`) and update the value in `videocraft/core/models_registry.py`.

### Hugging Face token (only if a download fails)

Most downloads need no account. If Hugging Face rate-limits you or a model requires sign-in
(the app tells you with a "Hugging Face access token" window), a **free** token fixes it:

1. Create a free account at [huggingface.co/join](https://huggingface.co/join).
2. Open [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → **Create new token** → type **Read**.
3. Copy the token (it starts with `hf_`) and paste it into the window, or into **Settings → Hugging Face**.

The token is stored in `~/.config/videocraftapp/hf_token` (owner-readable only) and is only sent to
huggingface.co. You can also set the `HF_TOKEN` environment variable instead.

## Architecture

```
VideoCraft
├── install.sh               # Linux installer (venv, launcher, `videocraft setup`)
├── pyproject.toml           # Package metadata, `ml` extra, `videocraft` command
├── videocraft/
│   ├── cli.py               # `videocraft` / `videocraft setup` entry point
│   ├── installer.py         # GPU detection + AI package installation
│   ├── main.py              # GUI entry: FFmpeg check, theme, window
│   ├── assets/              # Icons and custom QSS theme overrides
│   ├── core/
│   │   ├── config.py        # TOML config (platform-specific paths)
│   │   ├── ffmpeg.py        # FFmpeg/ffprobe resolution, thread count
│   │   ├── job.py           # Job dataclass (pipeline, params, status)
│   │   ├── job_queue.py     # Thread-safe queue with ML concurrency limits
│   │   ├── models_registry.py # Model metadata, download, verification
│   │   ├── nvenc.py         # NVENC detection and encoder selection
│   │   ├── process.py       # Cancellable subprocess runner
│   │   ├── theme.py         # qt-material theme + custom QSS
│   │   ├── vram_manager.py  # CUDA VRAM detection and tile sizing
│   │   └── worker.py        # QThread worker with multi-step pipelines
│   ├── processors/
│   │   ├── base_processor.py  # Abstract base (process() → log generator)
│   │   ├── converter.py       # FFmpeg format conversion
│   │   ├── frame_processor.py # Frame extraction/inference/re-encode base
│   │   ├── upscaler.py        # Real-ESRGAN upscaling
│   │   ├── denoiser.py        # SCUNet denoising
│   │   ├── colorizer.py       # DDColor colorization
│   │   ├── hdr_converter.py   # SDR → HDR10/HLG
│   │   ├── archs/             # Vendored model code (SCUNet, DDColor)
│   │   └── audio/
│   │       ├── vocal_remover.py # Demucs stem separation
│   │       └── upmixer.py       # Stereo → 5.1/7.1 upmix
│   └── ui/
│       ├── main_window.py   # QMainWindow with splitter layout
│       ├── panels/          # source, output, tools, queue, log panels
│       ├── dialogs/         # settings, model manager, pre-flight
│       └── widgets/         # drag-and-drop area
└── tests/
```

User data lives outside the code: config in `~/.config/videocraftapp/`, downloaded models in
`~/.local/share/videocraft/models/` (override with `$VIDEOCRAFT_MODELS_DIR`).

### Key Design Decisions

- **ML models are lazy-loaded** — never at import time; loaded inside `process()` on first use
- **Single concurrent ML job** — hard limit enforced by the job queue to prevent OOM
- **FFmpeg via `subprocess.Popen`** — never `os.system()`; all calls wrapped with timeout and cancellation
- **Frame processors share a common base** — `FrameProcessor` handles extraction, re-encoding, temp cleanup, and VRAM cache management
- **NVENC is probed at runtime** — a throwaway encode to `null` verifies each encoder actually works on the hardware
- **Graceful degradation** — missing ML deps fall back to pass-through (with a logged warning); missing NVENC falls back to software encoding

## Development

### Running Tests

```bash
pip install pytest
pytest tests/ -v

# headless machine (no display):
QT_QPA_PLATFORM=offscreen pytest tests/ -v
```

GitHub Actions runs the same suite on Python 3.11 and 3.12 for every push and pull request.

### Cutting a Release

1. Bump `__version__` in `videocraft/__init__.py` and move the `[Unreleased]` entries in
   `CHANGELOG.md` under the new version heading.
2. Merge to `main`, then push a matching tag: `git tag v0.2.0 && git push origin v0.2.0`.
3. The **Release** workflow runs the tests, builds the source and wheel packages, and publishes a
   GitHub release (marked pre-release for `0.x`) with install instructions. It fails if the tag does
   not match `__version__`. Use *Actions → Release → Run workflow* for a dry run that only builds.

### Project Structure for Contributors

- **`videocraft/core/`** — shared infrastructure (config, queue, FFmpeg, GPU detection)
- **`videocraft/processors/`** — tool implementations; each inherits `BaseProcessor` or `FrameProcessor`
- **`videocraft/ui/`** — PyQt6 panels, dialogs, and widgets
- **`tests/`** — unit tests for core components and processors

### Adding a New Processor

1. Create a class inheriting `BaseProcessor` (for direct FFmpeg tools) or `FrameProcessor` (for frame-based ML tools)
2. Implement `process(self, job)` yielding log line strings
3. Register it in `videocraft/core/worker.py` under `_PROCESSORS`
4. Add a settings tab in `videocraft/ui/panels/tools_panel.py`

## License

VideoCraft is free software, licensed under the [GNU General Public License v3.0](LICENSE). Third-party components keep their own licenses — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Acknowledgments

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) — video upscaling
- [SCUNet / KAIR](https://github.com/cszn/KAIR) — video denoising
- [DDColor](https://github.com/piddnad/DDColor) — colorization
- [Demucs](https://github.com/facebookresearch/demucs) — stem separation
- [FFmpeg](https://ffmpeg.org/) — video/audio processing
- [qt-material](https://github.com/UN-GCPDS/qt-material) — theming
- [qtawesome](https://github.com/pyqt/qtawesome) — icons
