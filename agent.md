# Agent Instructions — VideoCraft (AI Video Enhancement Suite)

## Project Overview

You are building **VideoCraft**, a desktop GUI application similar to HandBrake in layout and
workflow, but focused on AI-powered video and audio enhancement — inspired by UniFab. The app
provides a queue-based processing pipeline with a real-time CLI log panel, a source/output panel,
and modular AI tool tabs.

Target platforms: **Windows 10/11**, **macOS 12+**, **Linux (Ubuntu 22.04+)**

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| GUI Framework | **PyQt6** | Desktop UI, dockable panels, QProcess for live log |
| UI Theme | **qt-material** | Material Design dark/light themes, one-line application |
| Video Backend | **FFmpeg** (subprocess) | Format conversion, HDR, audio upmix, frame extraction |
| ML Runtime | **PyTorch 2.x + CUDA** | Inference for all AI models |
| Upscaling | **Real-ESRGAN** | 2x / 4x video upscaling (up to 4K/8K) |
| Denoising | **SCUNet** | Blind denoising, artifact/grain removal |
| Colorization | **DDColor** | Black-and-white to color conversion |
| Vocal Removal | **Demucs v4** | Music source separation, vocal stem isolation |
| Packaging | **PyInstaller** | Cross-platform binary distribution |
| Config | **TOML** (tomllib / tomli-w) | User settings and job presets |
| Logging | Python **logging** module | Timestamped logs streamed to the GUI log panel |

---

## Project Structure

```
videocraftapp/
├── agent.md                  ← This file
├── main.py                   ← Entry point
├── requirements.txt
├── README.md
│
├── ui/
│   ├── main_window.py        ← QMainWindow with splitter layout
│   ├── panels/
│   │   ├── source_panel.py   ← File picker, preview thumbnail, metadata display
│   │   ├── output_panel.py   ← Destination folder, format/codec selector
│   │   ├── tools_panel.py    ← Tab widget: one tab per AI tool
│   │   ├── queue_panel.py    ← Job queue table (filename, tool, status, progress)
│   │   └── log_panel.py      ← QPlainTextEdit with live stdout/stderr stream
│   ├── dialogs/
│   │   ├── settings_dialog.py
│   │   ├── model_manager_dialog.py
│   │   └── preflight_dialog.py   ← Pre-flight check: missing models, FFmpeg, CUDA
│   └── widgets/
│       ├── collapsible_section.py
│       ├── progress_bar_delegate.py
│       └── drag_drop_area.py
│
├── core/
│   ├── job.py                ← Job dataclass: source, output, pipeline, params, status
│   ├── job_queue.py          ← Thread-safe queue manager
│   │   worker.py             ← QThread worker, emits log lines + progress signals
│   ├── config.py             ← Load/save TOML config, default settings
│   └── vram_manager.py       ← CUDA VRAM detection + adaptive batch sizing
│
├── processors/
│   ├── base_processor.py     ← Abstract base: process(job) → generator of log lines
│   ├── converter.py          ← FFmpeg format conversion (1000+ formats via libav)
│   ├── upscaler.py           ← Real-ESRGAN frame-by-frame upscaling
│   ├── denoiser.py           ← SCUNet denoising pass
│   ├── colorizer.py          ← DDColor colorization
│   ├── hdr_converter.py      ← SDR→HDR10 via FFmpeg zscale + tonemap filters
│   └── audio/
│       ├── vocal_remover.py  ← Demucs stem separation
│       └── upmixer.py        ← FFmpeg channel layout upmix (stereo→5.1/7.1)
│
├── models/
│   └── .gitkeep              ← ML model weights download here at first run
│
└── assets/
    ├── icons/
    │   └── videocraftapp.ico
    └── themes/
        └── custom_overrides.qss  ← Small QSS patches on top of qt-material (log font, etc.)
```

---

## UI Layout (HandBrake-style)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Menu Bar:  File | Tools | Queue | View | Help                      │
├──────────────────────────────────┬──────────────────────────────────┤
│  SOURCE PANEL                    │  OUTPUT PANEL                    │
│  [ Open File(s) ] [ Open Folder ]│  Destination: [folder picker]   │
│  ┌──────────────────┐            │  Format:  [MP4 ▼]               │
│  │  video thumbnail │  metadata  │  Codec:   [H.265 ▼]             │
│  │  preview area    │  table     │  Quality: [RF 22 ─────────]     │
│  └──────────────────┘            │  Audio:   [AAC Stereo ▼]        │
├──────────────────────────────────┴──────────────────────────────────┤
│  TOOLS PANEL (Tab widget)                                           │
│  [ Upscaler ] [ Denoiser ] [ Colorizer ] [ HDR ] [ Audio ] [ Convert ]│
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Tool-specific settings (model selector, strength sliders, etc) ││
│  └─────────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│  QUEUE PANEL                                                        │
│  ┌────────────────┬────────────┬──────────┬────────────────────┐   │
│  │ Filename       │ Tool       │ Status   │ Progress           │   │
│  ├────────────────┼────────────┼──────────┼────────────────────┤   │
│  │ movie.mkv      │ Upscaler   │ ▶ Working│ ████████░░ 78%     │   │
│  │ old_film.mp4   │ Colorizer  │ Queued   │                    │   │
│  └────────────────┴────────────┴──────────┴────────────────────┘   │
│  [ ▶ Start Queue ] [ ⏸ Pause ] [ ✕ Cancel ] [ ↑ ↓ Reorder ]       │
├─────────────────────────────────────────────────────────────────────┤
│  LOG PANEL  (QPlainTextEdit, monospace, auto-scroll)                │
│  [2025-06-20 14:32:01] Starting Real-ESRGAN upscaling...           │
│  [2025-06-20 14:32:01] Extracting frames from movie.mkv...         │
│  [2025-06-20 14:32:04] Processing frame 0120/1840 (6.5%)...        │
└─────────────────────────────────────────────────────────────────────┘
```

The main window uses a **QSplitter (vertical)** so the user can resize the log panel.
Each major section (source, output, tools, queue, log) is a separate `QDockWidget` or
a fixed-position widget within a `QVBoxLayout` + `QSplitter`.

---

# ═══════════════════════════════════════════════════════════

# PHASED BUILD PLAN

# Build one phase at a time. Do not skip ahead

# Each phase must pass its acceptance criteria before starting the next

# ═══════════════════════════════════════════════════════════

## Phase 0 — Foundation

**Goal**: Bootable app shell with core infrastructure, config system, and logging.
No tools yet — just the skeleton everything else plugs into.

### Files to create

- `main.py` — Entry point, QApplication, qt-material theme init, FFmpeg existence check
- `ui/main_window.py` — QMainWindow with vertical QSplitter, placeholder panels, menu bar
- `ui/panels/log_panel.py` — QPlainTextEdit with auto-scroll, clear button, severity coloring
- `core/job.py` — Job dataclass (see below)
- `core/config.py` — TOML config load/save, default settings, platform-specific paths
- `core/vram_manager.py` — CUDA detection, VRAM probing, adaptive batch sizing
- `requirements.txt`
- `assets/themes/custom_overrides.qss` — Empty stub (filled in Phase 4)

### Job Dataclass (`core/job.py`)

```python
@dataclass
class Job:
    id: str                     # uuid4
    source_path: Path
    output_path: Path
    pipeline: list[str]         # ordered tool list, e.g. ["denoiser", "upscaler"]
                               # single-tool jobs use a 1-element list
    params: dict                # tool-specific settings dict (keys match pipeline order)
    status: str = "queued"      # queued | running | done | failed | cancelled
    progress: float = 0.0       # 0.0–1.0  (overall; per-step progress tracked internally)
    log_lines: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    cancelled: bool = False     # atomic cancellation flag checked by worker + processors
    intermediate_files: list[Path] = field(default_factory=list)  # for pipeline chaining
```

### VRAM Manager (`core/vram_manager.py`)

```python
class VRAMManager:
    """Detect available GPU memory and recommend safe batch/tile sizes."""

    def __init__(self):
        self.has_cuda: bool = torch.cuda.is_available()
        self.device: str = "cuda" if self.has_cuda else "cpu"
        self.total_vram_gb: float = 0.0
        self.recommended_batch: int = 1
        self.recommended_tile: int = 256

    def probe(self):
        """Query GPU VRAM and set safe defaults."""
        if self.has_cuda:
            self.total_vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
            self._set_recommendations()
        else:
            log_warning("No CUDA GPU detected — running on CPU (slow)")

    def _set_recommendations(self):
        if self.total_vram_gb >= 24:
            self.recommended_batch, self.recommended_tile = 4, 512
        elif self.total_vram_gb >= 12:
            self.recommended_batch, self.recommended_tile = 2, 256
        elif self.total_vram_gb >= 6:
            self.recommended_batch, self.recommended_tile = 1, 128
        else:
            self.recommended_batch, self.recommended_tile = 1, 96
```

### Cancellation Architecture

Every processor and the worker thread must support graceful cancellation:

1. **Worker thread** checks `job.cancelled` between each yielded log line:

   ```python
   def run(self):
       processor = get_processor(self.job.tool)
       try:
           for line in processor.process(self.job):
               if self.job.cancelled:
                   self._cleanup()
                   self.job.status = "cancelled"
                   return
               self.log_line.emit(line)
       except Exception as e:
           self.job_failed.emit(self.job, str(e))
   ```

2. **Subprocess cancellation**: Each processor wraps FFmpeg/model calls in a cancellable context:

   ```python
   class CancellableProcess:
       def __init__(self, job: Job, cmd: list[str]):
           self.job = job
           self.process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)

       def cancel(self):
           if self.process and self.process.poll() is None:
               self.process.terminate()
               try:
                   self.process.wait(timeout=3)
               except TimeoutExpired:
                   self.process.kill()

       def __enter__(self):
           return self

       def __exit__(self, *args):
           self.cancel()  # always clean up
   ```

3. **Temp directory cleanup**: Use `shutil.rmtree()` in a `finally` block after every job:

   ```python
   def process(self, job: Job):
       temp_dir = tempfile.mkdtemp(prefix="videocraft_")
       try:
           yield from self._do_work(temp_dir, job)
       finally:
           shutil.rmtree(temp_dir, ignore_errors=True)
   ```

### Acceptance Criteria

- [ ] App launches, shows empty window with menu bar and placeholder panels
- [ ] Log panel accepts and displays colored log lines
- [ ] Config loads/saves to platform-specific path
- [ ] VRAM manager detects GPU (or logs CPU fallback)
- [ ] FFmpeg existence check on startup (error dialog if missing)

---

## Phase 1 — First Working Tool (Format Converter)

**Goal**: End-to-end working job pipeline: source → queue → worker → log → output.
Format conversion is FFmpeg-only (no ML), so it validates the entire architecture.

### Files to create

- `core/worker.py` — QThread worker with signals, cancellation support, temp cleanup
- `core/job_queue.py` — Thread-safe queue with start/pause/cancel/reorder
- `processors/base_processor.py` — Abstract base class
- `processors/converter.py` — FFmpeg format conversion processor
- `ui/panels/source_panel.py` — File picker with drag-and-drop, ffprobe metadata
- `ui/panels/output_panel.py` — Output folder picker, format/codec dropdowns
- `ui/panels/queue_panel.py` — Queue table with progress bars, status, cancel button

### Worker Thread (`core/worker.py`)

```python
class Worker(QThread):
    log_line   = pyqtSignal(str)
    progress   = pyqtSignal(float)
    job_done   = pyqtSignal(object)
    job_failed = pyqtSignal(object, str)

    def __init__(self, job: Job):
        super().__init__()
        self.job = job

    def run(self):
        self.job.status = "running"
        processor = get_processor(self.job.pipeline[0])
        try:
            for line in processor.process(self.job):
                if self.job.cancelled:
                    self.job.status = "cancelled"
                    self.log_line.emit("[CANCELLED] Job cancelled by user")
                    return
                self.log_line.emit(line)
            self.job.status = "done"
            self.job_done.emit(self.job)
        except Exception as e:
            self.job.status = "failed"
            self.job_failed.emit(self.job, str(e))
```

### FFmpeg Integration Rules

- Always call FFmpeg via `subprocess.Popen` with `stdout=PIPE, stderr=PIPE, text=True`
- Parse FFmpeg's `stderr` for progress: use `time=` parsed against total duration (from ffprobe)
  rather than frame counts — frame counts break with multi-stream or filter-graph encodes
- Progress regex: `r"time=(\d+):(\d+):(\d+\.\d+)"` → convert to seconds → divide by total duration
- Always include `-y` to auto-overwrite, `-hide_banner -loglevel info` for clean output
- Use `tempfile.mkdtemp()` for intermediates; clean in `finally` block
- Wrap all Popen calls with timeout; handle `TimeoutExpired`

### Output Backup Rule

Before overwriting an existing output file, rename it with a timestamp suffix:

```python
def backup_existing(path: Path):
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_stem(f"{path.stem}_{ts}")
        path.rename(backup)
```

### Acceptance Criteria

- [ ] User can add a video file, pick output format, and start a conversion job
- [ ] Queue panel shows job with real-time progress bar
- [ ] Log panel shows timestamped FFmpeg progress lines
- [ ] Job completes with playable output file
- [ ] Cancelling mid-job kills FFmpeg, cleans temp files, marks job as cancelled
- [ ] Existing output files are backed up before overwrite
- [ ] Works without CUDA (FFmpeg is CPU-only)

---

## Phase 2 — ML Pipeline Tools

**Goal**: Frame-based AI processors (upscaler, denoiser, colorizer) with VRAM management,
pipeline chaining, and pre-flight model checks.

### Files to create

- `processors/upscaler.py` — Real-ESRGAN upscaler
- `processors/denoiser.py` — SCUNet denoiser
- `processors/colorizer.py` — DDColor colorizer
- `ui/dialogs/preflight_dialog.py` — Pre-flight model availability check

### Pipeline Chaining

Jobs can chain multiple tools. The worker executes each step sequentially, passing the
output of one step as the input to the next:

```python
def run(self):
    current_source = self.job.source_path
    for i, tool_name in enumerate(self.job.pipeline):
        if self.job.cancelled:
            self.job.status = "cancelled"
            return

        # Create intermediate output path for multi-step pipelines
        if i < len(self.job.pipeline) - 1:
            stem = self.job.source_path.stem
            ext = self.job.source_path.suffix
            intermediate = self.job.output_path.parent / f"{stem}_step{i}_{tool_name}{ext}"
            self.job.intermediate_files.append(intermediate)
            step_output = intermediate
        else:
            step_output = self.job.output_path

        processor = get_processor(tool_name)
        step_job = replace(self.job, output_path=step_output, source_path=current_source)
        yield from processor.process(step_job)
        current_source = step_output

    # Clean up intermediate files after successful completion
    if self.job.status == "done":
        for f in self.job.intermediate_files:
            if f.exists():
                f.unlink()
```

### Pre-Flight Check

Before starting the queue, run a pre-flight dialog that checks:

1. **FFmpeg** is on PATH (or at configured path)
2. **Required models** exist for every tool in the queue
3. **CUDA availability** (warn if CPU-only for ML tools)
4. **Disk space** — estimate output size vs available space

Missing models trigger a download prompt (not a crash). The user can:

- Download now (shows QProgressDialog)
- Skip the job (remove from queue)
- Cancel the entire queue

### VRAM Management in Processors

Each ML processor queries `VRAMManager` before inference:

```python
def process(self, job: Job):
    vram = get_vram_manager()
    batch_size = vram.recommended_batch
    tile_size = vram.recommended_tile

    # If user override is set, clamp it to safe maximum
    user_tile = job.params.get("tile_size", tile_size)
    safe_tile = min(user_tile, tile_size)

    # Clear CUDA cache before and after each job to prevent memory leaks
    if vram.has_cuda:
        torch.cuda.empty_cache()
    try:
        yield from self._do_inference(batch_size, safe_tile, job)
    finally:
        if vram.has_cuda:
            torch.cuda.empty_cache()
```

### Model Download & Management

- On first run of each tool, check if model weights exist in `models/` directory
- If missing, show `QProgressDialog` during download with cancel button
- Store SHA256 hashes in `models/checksums.json` and verify on load
- **Model Manager dialog** (`ui/dialogs/model_manager_dialog.py`) shows:
  - Which models are downloaded (green checkmark) vs not (grey dash)
  - File size and disk usage
  - Download / Delete buttons per model

### Colorizer Note

DDColor's last meaningful update was ~2021. It works but has limited ecosystem support.
If the user reports poor results, suggest **Deoldify** as an alternative model backend.
For now, implement DDColor as specified; add Deoldify as a future option.

### Concurrent Job Safety

- **Hard limit of 1 concurrent ML job** — running 2+ GPU jobs will OOM most systems
- CPU-only jobs (format conversion, HDR) can run concurrently if `concurrent_jobs > 1`
- The job queue enforces this: before starting a job, check if any ML job is already running

### Acceptance Criteria

- [ ] Upscaler processes a real video end-to-end (frame extract → inference → recompose)
- [ ] Denoiser removes visible noise without destroying detail
- [ ] Colorizer preserves luminance, only modifies chroma channels
- [ ] Pipeline chaining works (e.g., denoise → upscale produces single output file)
- [ ] VRAM manager auto-scales batch/tile size based on GPU memory
- [ ] Pre-flight dialog catches missing models before queue starts
- [ ] Cancelling an ML job kills inference, cleans temp frames, frees CUDA memory
- [ ] Only 1 ML job runs at a time regardless of `concurrent_jobs` setting

---

## Phase 3 — Advanced Tools

**Goal**: HDR converter, audio tools, and full tools panel wiring.

### Files to create

- `processors/hdr_converter.py` — SDR→HDR via FFmpeg zscale + tonemap
- `processors/audio/vocal_remover.py` — Demucs stem separation
- `processors/audio/upmixer.py` — FFmpeg channel upmix
- `ui/panels/tools_panel.py` — Tab widget wiring all tools' settings UIs

### HDR Converter (`processors/hdr_converter.py`)

- **Method**: FFmpeg-only (no ML model needed)
- **Pipeline**:

  ```
  ffmpeg -i input.mp4
    -vf "zscale=t=linear:npl=100,format=gbrpf32le,
         zscale=p=bt2020:t=st2084:m=bt2020nc:r=tv,
         tonemap=hable,
         zscale=t=bt2020-10:m=bt2020nc:r=tv,
         format=yuv420p10le"
    -color_primaries bt2020 -color_trc smpte2084
    -colorspace bt2020nc output_hdr.mp4
  ```

- **Settings UI**: Target format (HDR10 / HLG), peak brightness nits (400/1000/4000),
  tonemap algorithm (hable / reinhard / mobius)

### Vocal Remover (`processors/audio/vocal_remover.py`)

- **Model**: Demucs v4 (htdemucs_ft for fine-tuned separation)
- **Stems**: Vocals, Drums, Bass, Other (user selects which to keep or discard)
- **Pipeline**:
  1. Extract audio from video via FFmpeg (`-vn -acodec pcm_s16le`)
  2. Run `python -m demucs.separate` on the extracted WAV
  3. Re-mux chosen stems back into the video
- **Settings UI**: Stem checkboxes, output format (WAV / FLAC / AAC), job type
  ("Remove Vocals" quick mode vs "Full Separation" mode)

### Audio Upmixer (`processors/audio/upmixer.py`)

- **Method**: FFmpeg channel manipulation + `aformat` filters
- **Modes**: Stereo → 5.1 Surround (EAC3), Stereo → 7.1 Surround (DTS-HD MA)
- **Pipeline**:

  ```
  ffmpeg -i input.mp4
    -c:v copy
    -af "aformat=channel_layouts=5.1,
         channelmap=channel_layout=5.1"
    -c:a eac3 -b:a 640k output.mp4
  ```

- **Settings UI**: Target layout dropdown, bitrate selector, LFE gain slider

### Acceptance Criteria

- [ ] HDR conversion produces valid HDR10 output (verifiable with ffprobe)
- [ ] Vocal remover isolates stems and re-muxes correctly
- [ ] Audio upmixer produces valid 5.1/7.1 output
- [ ] Tools panel tabs show correct settings UI for each tool
- [ ] All tools appear in the pipeline selector for chaining

---

## Phase 4 — Polish & Distribution

**Goal**: Settings dialog, model manager, theme customization, packaging.

### Files to create

- `ui/dialogs/settings_dialog.py` — App settings (theme, FFmpeg path, GPU, concurrent jobs)
- `ui/dialogs/model_manager_dialog.py` — Model download manager
- `ui/widgets/collapsible_section.py` — Collapsible UI sections for tool settings
- `ui/widgets/progress_bar_delegate.py` — Custom progress bar for queue table
- `ui/widgets/drag_drop_area.py` — Drag-and-drop file support
- `assets/themes/custom_overrides.qss` — Final QSS overrides
- PyInstaller spec file

### Configuration System (`core/config.py`)

Use TOML for all settings. Default config location:

- Windows: `%APPDATA%/VideoCraft/config.toml`
- macOS: `~/Library/Application Support/VideoCraft/config.toml`
- Linux: `~/.config/videocraftapp/config.toml`

```toml
[general]
theme = "dark_orange.xml"
default_output_dir = ""
concurrent_jobs = 1

[ffmpeg]
path = "ffmpeg"       # "ffmpeg" (from PATH) or absolute path
threads = 0           # 0 = auto

[gpu]
device = "auto"       # "auto" | "cuda:0" | "cpu"
tile_size = 256       # for low-VRAM systems

[upscaler]
default_scale = 4
default_model = "RealESRGAN_x4plus"

[colorizer]
default_style = "artistic"
saturation = 1.0

[hdr]
peak_nits = 1000
tonemap = "hable"
```

### GUI Theme & Style (qt-material)

Apply qt-material in `main.py` **before** the main window is shown, and **after**
`QApplication` is created. Never apply it after widgets are already rendered.

```python
import sys
from PyQt6.QtWidgets import QApplication
from qt_material import apply_stylesheet
from ui.main_window import MainWindow

app = QApplication(sys.argv)

apply_stylesheet(app, theme='dark_orange.xml', extra={
    'font_family':        'Segoe UI',
    'font_size':          '13px',
    'density_scale':      '-1',
    'primaryColor':       '#e85d04',
    'primaryLightColor':  '#ff8c42',
    'secondaryColor':     '#1e1e1e',
    'secondaryLightColor':'#2d2d2d',
    'secondaryDarkColor': '#141414',
})

with open('assets/themes/custom_overrides.qss', 'r') as f:
    app.setStyleSheet(app.styleSheet() + f.read())

window = MainWindow()
window.show()
sys.exit(app.exec())
```

### Manual Overrides (`assets/themes/custom_overrides.qss`)

```css
QPlainTextEdit#logPanel {
    font-family: "Consolas", "Courier New", "DejaVu Sans Mono", monospace;
    font-size: 11pt;
    background-color: #111111;
    color: #d4d4d4;
    border: 1px solid #333333;
}

QTableWidget {
    gridline-color: #2a2a2a;
}
QTableWidget::item {
    padding: 4px 8px;
}

QProgressBar {
    border-radius: 3px;
    text-align: center;
    height: 14px;
}
QProgressBar::chunk {
    background-color: #e85d04;
    border-radius: 3px;
}

QTabBar::tab:selected {
    font-weight: 600;
    border-bottom: 2px solid #e85d04;
}
```

### Icons (qtawesome)

```python
import qtawesome as qta

btn_start  = QPushButton(qta.icon('mdi.play-circle',  color='#e85d04'), 'Start Queue')
btn_pause  = QPushButton(qta.icon('mdi.pause-circle', color='#aaaaaa'), 'Pause')
btn_cancel = QPushButton(qta.icon('mdi.close-circle', color='#aaaaaa'), 'Cancel')
btn_open   = QPushButton(qta.icon('mdi.folder-open',  color='#e85d04'), 'Open File')
```

### Log Panel Coloring

```python
LOG_COLORS = {
    'INFO':    '#d4d4d4',
    'WARNING': '#f0a500',
    'ERROR':   '#f44747',
    'SUCCESS': '#4ec9b0',
    'FRAME':   '#9cdcfe',
}

def append_log(self, line: str):
    color = LOG_COLORS.get('ERROR' if 'error' in line.lower() else 'INFO', '#d4d4d4')
    self.log_panel.appendHtml(f'<span style="color:{color};">{line}</span>')
```

### Acceptance Criteria

- [ ] Settings dialog persists all preferences to TOML
- [ ] Runtime theme switching works without restart
- [ ] Model manager shows/download/deletes all models
- [ ] Drag-and-drop files onto source panel or main window
- [ ] PyInstaller builds working binaries for all 3 platforms
- [ ] Full end-to-end test: denoise → upscale → HDR pipeline on a real video

---

## AI Tools — Feature Specifications (Reference)

### 1. Video Upscaler (`processors/upscaler.py`)

- **Model**: Real-ESRGAN (RealESRGAN_x4plus for general video, RealESRGAN_x4plus_anime for animation)
- **Scale factors**: 2x, 4x (chain two 4x passes for 8x / 16K if needed)
- **Pipeline**:
  1. Use FFmpeg to extract frames as PNG sequence into a temp folder
  2. Run Real-ESRGAN inference on each frame (batched per VRAMManager recommendations)
  3. Re-encode frames back into video with FFmpeg, preserving original audio
- **Settings UI**: Scale factor radio buttons, model selector dropdown, tile size (for low-VRAM)
- **GPU**: Auto-detect CUDA via VRAMManager; fall back to CPU with a warning

### 2. Denoiser (`processors/denoiser.py`)

- **Model**: SCUNet (scunet_color_real_psnr for real-world noise/compression artifacts)
- **Pipeline**: Same frame-extraction → inference → recompose as upscaler
- **Settings UI**: Noise level slider (1–50), artifact removal toggle (JPEG/blocking artifacts)

### 3. Colorizer (`processors/colorizer.py`)

- **Model**: DDColor (ddcolor_artistic or ddcolor_modelscope)
- **Pipeline**: Frame extraction → DDColor inference → recompose with FFmpeg
- **Settings UI**: Style selector (Artistic / Natural), saturation slider
- **Note**: Preserve luminance from original grayscale; only replace chroma channels (YCbCr)
- **Future**: Consider Deoldify as an alternative backend if DDColor results are unsatisfactory

### 4. HDR Converter (`processors/hdr_converter.py`)

- See Phase 3 specification above

### 5. Vocal Remover / Audio Separator (`processors/audio/vocal_remover.py`)

- See Phase 3 specification above

### 6. Audio Upmixer (`processors/audio/upmixer.py`)

- See Phase 3 specification above

### 7. Format Converter (`processors/converter.py`)

- **Backend**: FFmpeg subprocess
- **Supported outputs**: MP4, MKV, MOV, AVI, WebM, GIF, MP3, AAC, FLAC, WAV
- **Preset system**: Fast, Balanced, Quality (maps to CRF values + encoder presets)
- **Settings UI**: Container format, video codec (H.264, H.265, AV1, VP9), audio codec,
  CRF/quality slider, resolution override, FPS override

---

## Core Architecture Rules

### Processor Base (`processors/base_processor.py`)

```python
from abc import ABC, abstractmethod
from core.job import Job

class BaseProcessor(ABC):
    @abstractmethod
    def process(self, job: Job):
        """Yield log line strings. Update job.progress in-place.
        Check job.cancelled periodically and stop early if set."""
        ...
```

### Signals Pattern

```python
class Worker(QThread):
    log_line   = pyqtSignal(str)
    progress   = pyqtSignal(float)
    job_done   = pyqtSignal(object)
    job_failed = pyqtSignal(object, str)

    def run(self):
        self.job.status = "running"
        processor = get_processor(self.job.pipeline[0])
        try:
            for line in processor.process(self.job):
                if self.job.cancelled:
                    self.job.status = "cancelled"
                    self.log_line.emit("[CANCELLED] Job cancelled by user")
                    return
                self.log_line.emit(line)
            self.job.status = "done"
            self.job_done.emit(self.job)
        except Exception as e:
            self.job.status = "failed"
            self.job_failed.emit(self.job, str(e))
```

---

## Requirements (`requirements.txt`)

```
PyQt6>=6.6.0
qt-material>=2.14.0
qtawesome>=1.3.0
torch>=2.1.0
torchvision>=0.16.0
basicsr>=1.4.2
realesrgan>=0.3.0
demucs>=4.0.0
ddcolor>=0.1.0
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
tomli-w>=1.0.0
requests>=2.31.0
tqdm>=4.66.0
```

> **Note**: FFmpeg must be installed separately and available on PATH, OR bundled as a binary
> in `assets/bin/ffmpeg[.exe]`. Check for FFmpeg at startup and show a clear error dialog if
> not found, with a link to <https://ffmpeg.org/download.html>.

---

## Error Handling Rules

- **Never crash silently.** Catch all exceptions in the worker thread and emit `job_failed`
- Display errors in the log panel in red text AND in a non-blocking status bar message
- If a model file is missing or corrupt, prompt the user to re-download (don't crash)
- If FFmpeg is not found, show a prominent error dialog on startup (not buried in a log)
- If CUDA is not available, log a warning and continue with CPU (do NOT refuse to run)
- Wrap all `subprocess.Popen` calls with timeout and handle `TimeoutExpired`
- On OOM during inference, reduce batch size by half and retry once; if it OOMs again,
  fall back to CPU with a clear warning

---

## Coding Conventions

- Python 3.11+, type hints on all function signatures
- Follow PEP 8; max line length 100 characters
- Each file has a module docstring explaining its role
- No business logic in UI files — UI only calls `core/` and `processors/`
- All long operations run in `QThread` — never block the main/GUI thread
- Use `pathlib.Path` everywhere, never raw string paths
- Log format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- Keep each class in its own file unless it's a tiny helper

---

## What NOT to Do

- Do NOT use `os.system()` — always use `subprocess.Popen` or `subprocess.run`
- Do NOT use `tkinter` or any other GUI library — PyQt6 only
- Do NOT hard-code paths — use `pathlib` and the config system
- Do NOT load ML models at import time — lazy-load them inside `process()` on first use
- Do NOT put FFmpeg command strings inline all over the codebase —
  each processor owns its own FFmpeg command construction
- Do NOT use threads other than `QThread` for anything that touches the GUI
- Do NOT write a full custom `.qss` from scratch — qt-material handles the base theme;
  only add targeted overrides in `custom_overrides.qss`
- Do NOT call `apply_stylesheet()` after the main window is already shown — apply it
  in `main.py` before `window.show()`
- Do NOT run more than 1 ML job concurrently — it will OOM
- Do NOT skip the pre-flight check — always verify models exist before starting ML jobs
- Do NOT leave temp directories behind — every `mkdtemp()` must have a matching `rmtree()` in `finally`

---

## Testing Checklist (per tool)

Before marking a tool complete, verify:

- [ ] Processes a real video file end-to-end without crashing
- [ ] Log panel shows timestamped progress lines during processing
- [ ] Progress bar in the queue panel updates in real time
- [ ] Job status changes: queued → running → done (or failed with error message)
- [ ] Output file exists and is playable after job completes
- [ ] Cancelling a job mid-way stops the subprocess and cleans up temp files
- [ ] Works on CPU if no CUDA GPU is present
- [ ] Pipeline chaining: tool works as both first and intermediate step in a multi-tool pipeline
- [ ] Pre-flight check correctly reports model availability
