# Implementation Plan: VideoCraft (AI Video Enhancement Suite)

## Overview

Build a cross-platform PyQt6 desktop app for AI-powered video/audio enhancement. Queue-based pipeline with real-time logging, modular AI tool tabs, and HandBrake-style layout. 4 phases, ~25 tasks, each 1-5 files.

## Architecture Decisions

- **Bottom-up dependency order**: core types → processors → worker/queue → UI panels → wiring
- **Vertical slicing within phases**: each phase delivers a testable end-to-end flow
- **ML models lazy-loaded**: never at import time; loaded inside `process()` on first use
- **Single concurrent ML job**: hard limit enforced by job queue
- **FFmpeg via subprocess.Popen**: never `os.system()`; all calls wrapped with timeout + cancellation
- **FFmpeg bundled**: platform-specific binaries in `assets/bin/ffmpeg[.exe]`; checked before PATH fallback
- **Colorization backends**: DDColor and Deoldify — user chooses in tool settings; both lazy-loaded
- **Model downloads**: fallback chain — HuggingFace → GitHub releases → direct URLs
- **Python 3.11+**: minimum target for cross-platform compatibility

## Task List

---

### Phase 0: Foundation

**Goal**: Bootable app shell with config, logging, VRAM detection, and FFmpeg check.

#### Task 1: Project scaffolding + requirements

**Description:** Create `requirements.txt` and empty asset stubs so the project is importable.

**Acceptance criteria:**
- [ ] `requirements.txt` lists all dependencies with version pins
- [ ] `assets/themes/custom_overrides.qss` exists (empty stub)
- [ ] `models/.gitkeep` exists
- [ ] `assets/bin/.gitkeep` exists (FFmpeg binaries placed here for distribution)

**Verification:**
- [ ] `pip install -r requirements.txt` succeeds (dry-run or venv)

**Dependencies:** None

**Files likely touched:**
- `requirements.txt`
- `assets/themes/custom_overrides.qss`
- `models/.gitkeep`
- `assets/bin/.gitkeep`

---

#### Task 2: Job dataclass (`core/job.py`)

**Description:** Define the `Job` dataclass with all fields (id, source, output, pipeline, params, status, progress, log_lines, cancelled, intermediate_files).

**Acceptance criteria:**
- [ ] `Job` dataclass has all specified fields with correct types and defaults
- [ ] `id` is `uuid4` string, `created_at` defaults to `datetime.now()`
- [ ] `cancelled` defaults to `False`, `status` defaults to `"queued"`

**Verification:**
- [ ] Unit test: create Job, verify defaults
- [ ] Unit test: verify all fields are type-hinted

**Dependencies:** None

**Files likely touched:**
- `core/__init__.py`
- `core/job.py`

---

#### Task 3: Config system (`core/config.py`)

**Description:** TOML config load/save with platform-specific paths and sensible defaults.

**Acceptance criteria:**
- [ ] Config loads from platform-specific path (Windows/macOS/Linux)
- [ ] Config saves all settings to TOML
- [ ] Missing config file creates defaults on first run
- [ ] All sections from spec covered: general, ffmpeg, gpu, upscaler, colorizer, hdr

**Verification:**
- [ ] Unit test: create config, save, reload, verify round-trip
- [ ] Unit test: missing file creates defaults

**Dependencies:** Task 2 (none strictly, but ordered for core/ init)

**Files likely touched:**
- `core/config.py`

---

#### Task 4: VRAM manager (`core/vram_manager.py`)

**Description:** CUDA detection, VRAM probing, adaptive batch/tile recommendations.

**Acceptance criteria:**
- [ ] Detects CUDA availability via `torch.cuda.is_available()`
- [ ] Probes total VRAM and sets batch/tile recommendations per spec thresholds
- [ ] Logs warning and falls back to CPU when no CUDA

**Verification:**
- [ ] Unit test: CPU-only path sets `has_cuda=False`, `device="cpu"`
- [ ] Unit test (mock): VRAM >= 24GB → batch=4, tile=512

**Dependencies:** None

**Files likely touched:**
- `core/vram_manager.py`

---

#### Task 5: Log panel (`ui/panels/log_panel.py`)

**Description:** QPlainTextEdit with auto-scroll, clear button, severity coloring.

**Acceptance criteria:**
- [ ] Displays log lines with color coding (INFO/WARNING/ERROR/SUCCESS/FRAME)
- [ ] Auto-scrolls to bottom on new lines
- [ ] Clear button resets content

**Verification:**
- [ ] Manual: app shows log panel, colored lines appear, clear works

**Dependencies:** None

**Files likely touched:**
- `ui/__init__.py`
- `ui/panels/__init__.py`
- `ui/panels/log_panel.py`

---

#### Task 6: Main window shell (`ui/main_window.py` + `main.py`)

**Description:** QMainWindow with vertical QSplitter, placeholder panels, menu bar, qt-material theme, FFmpeg existence check.

**Acceptance criteria:**
- [ ] App launches and shows window with menu bar and placeholder panels
- [ ] qt-material theme applied before `window.show()`
- [ ] FFmpeg check: bundled binary in `assets/bin/` first, then PATH fallback; error dialog if neither found
- [ ] Log panel wired and functional
- [ ] QSplitter allows resizing log panel

**Verification:**
- [ ] Manual: app launches, shows UI, log panel works
- [ ] Manual: missing FFmpeg shows error dialog

**Dependencies:** Tasks 2-5

**Files likely touched:**
- `main.py`
- `ui/main_window.py`

---

#### Checkpoint: Phase 0

- [ ] App launches with themed UI, menu bar, log panel, and placeholder panels
- [ ] Config loads/saves to platform-specific path
- [ ] VRAM manager detects GPU (or logs CPU fallback)
- [ ] FFmpeg check works on startup
- [ ] All unit tests pass

---

### Phase 1: First Working Tool (Format Converter)

**Goal**: End-to-end job pipeline: source → queue → worker → log → output.

#### Task 7: Processor base class (`processors/base_processor.py`)

**Description:** Abstract base class defining `process(job)` → generator of log lines.

**Acceptance criteria:**
- [ ] `BaseProcessor` is abstract with `process()` method
- [ ] `process()` yields log line strings
- [ ] Checks `job.cancelled` periodically

**Verification:**
- [ ] Unit test: cannot instantiate BaseProcessor directly
- [ ] Unit test: subclass can implement process()

**Dependencies:** Task 2 (Job dataclass)

**Files likely touched:**
- `processors/__init__.py`
- `processors/base_processor.py`

---

#### Task 8: FFmpeg converter processor (`processors/converter.py`)

**Description:** FFmpeg format conversion processor with progress parsing, cancellation, temp cleanup, and output backup.

**Acceptance criteria:**
- [ ] Converts video via FFmpeg subprocess with progress tracking
- [ ] Parses `time=` from FFmpeg stderr for real-time progress
- [ ] Cancels subprocess on `job.cancelled`
- [ ] Backs up existing output files before overwrite
- [ ] Cleans temp files in `finally` block

**Verification:**
- [ ] Manual: convert a real video file, verify output playable
- [ ] Manual: cancel mid-job, verify FFmpeg killed and temp cleaned
- [ ] Unit test: backup_existing() renames file with timestamp

**Dependencies:** Tasks 2, 7

**Files likely touched:**
- `processors/converter.py`

---

#### Task 9: Worker thread (`core/worker.py`)

**Description:** QThread worker with signals (log_line, progress, job_done, job_failed), cancellation support, temp cleanup.

**Acceptance criteria:**
- [ ] Worker emits `log_line` for each yielded log line
- [ ] Worker checks `job.cancelled` between lines
- [ ] Worker emits `job_done` or `job_failed` on completion
- [ ] Temp directory cleaned in `finally` block

**Verification:**
- [ ] Unit test: worker emits signals in correct order
- [ ] Manual: run a conversion job, verify signals fire

**Dependencies:** Tasks 2, 7, 8

**Files likely touched:**
- `core/worker.py`

---

#### Task 10: Job queue (`core/job_queue.py`)

**Description:** Thread-safe queue with add, start, pause, cancel, reorder. Enforces 1 concurrent ML job limit.

**Acceptance criteria:**
- [ ] Queue is thread-safe (uses locks or QMutex)
- [ ] Supports add, start, pause, cancel, reorder operations
- [ ] Enforces 1 concurrent ML job limit
- [ ] CPU-only jobs can run concurrently if `concurrent_jobs > 1`

**Verification:**
- [ ] Unit test: add 3 jobs, verify queue order
- [ ] Unit test: cancel job, verify status changes
- [ ] Manual: start queue, verify jobs process in order

**Dependencies:** Tasks 2, 9

**Files likely touched:**
- `core/job_queue.py`

---

#### Task 11: Source panel (`ui/panels/source_panel.py`)

**Description:** File picker with drag-and-drop, ffprobe metadata display, thumbnail preview.

**Acceptance criteria:**
- [ ] "Open File(s)" button opens file dialog for video files
- [ ] Drag-and-drop accepts video files
- [ ] Displays metadata (duration, resolution, codec) via ffprobe
- [ ] Shows thumbnail preview

**Verification:**
- [ ] Manual: open a video file, verify metadata and thumbnail
- [ ] Manual: drag-and-drop a file, verify it loads

**Dependencies:** None (independent UI component)

**Files likely touched:**
- `ui/panels/source_panel.py`

---

#### Task 12: Output panel (`ui/panels/output_panel.py`)

**Description:** Output folder picker, format/codec dropdowns, quality slider.

**Acceptance criteria:**
- [ ] Folder picker sets output directory
- [ ] Format dropdown lists MP4, MKV, MOV, AVI, WebM, etc.
- [ ] Codec dropdown lists H.264, H.265, AV1, VP9
- [ ] Quality/CRF slider maps to encoder settings

**Verification:**
- [ ] Manual: pick output folder, select format/codec, verify settings

**Dependencies:** None (independent UI component)

**Files likely touched:**
- `ui/panels/output_panel.py`

---

#### Task 13: Queue panel (`ui/panels/queue_panel.py`)

**Description:** Queue table with filename, tool, status, progress bar, cancel button.

**Acceptance criteria:**
- [ ] Table shows jobs with columns: filename, tool, status, progress
- [ ] Progress bar updates in real time
- [ ] Cancel button sets `job.cancelled = True`
- [ ] Start/pause/cancel controls at bottom of panel

**Verification:**
- [ ] Manual: add job to queue, verify table shows it
- [ ] Manual: start job, verify progress bar updates
- [ ] Manual: cancel job, verify status changes

**Dependencies:** Tasks 10, 11, 12

**Files likely touched:**
- `ui/panels/queue_panel.py`

---

#### Task 14: Wire Phase 1 panels + main window

**Description:** Integrate source, output, queue panels into main window. Wire signals between panels, queue, and worker.

**Acceptance criteria:**
- [ ] Source panel file selection creates job in queue
- [ ] Output panel settings applied to job
- [ ] Queue panel controls start/pause/cancel worker
- [ ] Log panel receives log lines from worker
- [ ] Full end-to-end: add file → start → convert → output playable

**Verification:**
- [ ] Manual: full end-to-end conversion of a real video
- [ ] Manual: cancel mid-job, verify cleanup
- [ ] Manual: existing output backed up before overwrite

**Dependencies:** Tasks 6, 9-13

**Files likely touched:**
- `ui/main_window.py`
- `core/worker.py` (signal wiring)

---

#### Checkpoint: Phase 1

- [ ] User can add a video, pick output format, and start conversion
- [ ] Queue panel shows real-time progress
- [ ] Log panel shows timestamped FFmpeg lines
- [ ] Job completes with playable output
- [ ] Cancel kills FFmpeg, cleans temp, marks cancelled
- [ ] Existing output backed up before overwrite
- [ ] Works without CUDA

---

### Phase 2: ML Pipeline Tools

**Goal**: Frame-based AI processors with VRAM management, pipeline chaining, pre-flight checks.

#### Task 15: Upscaler processor (`processors/upscaler.py`)

**Description:** Real-ESRGAN frame-by-frame upscaling with VRAM-aware batching.

**Acceptance criteria:**
- [ ] Extracts frames via FFmpeg to temp PNG sequence
- [ ] Runs Real-ESRGAN inference with VRAMManager batch/tile settings
- [ ] Re-encodes frames to video preserving audio
- [ ] Supports 2x and 4x scale factors
- [ ] Clears CUDA cache before/after each job

**Verification:**
- [ ] Manual: upscale a real video, verify output resolution and quality
- [ ] Manual: cancel mid-job, verify temp frames cleaned

**Dependencies:** Tasks 2, 4, 7

**Files likely touched:**
- `processors/upscaler.py`

---

#### Task 16: Denoiser processor (`processors/denoiser.py`)

**Description:** SCUNet denoising with noise level control and artifact removal.

**Acceptance criteria:**
- [ ] Extracts frames, runs SCUNet inference, re-encodes
- [ ] Noise level slider (1-50) maps to model parameters
- [ ] Artifact removal toggle for JPEG/blocking artifacts
- [ ] Respects VRAMManager recommendations

**Verification:**
- [ ] Manual: denoise a noisy video, verify quality improvement

**Dependencies:** Tasks 2, 4, 7

**Files likely touched:**
- `processors/denoiser.py`

---

#### Task 17: Colorizer processor (`processors/colorizer.py`)

**Description:** Colorization processor supporting both DDColor and Deoldify backends. User chooses model in tool settings.

**Acceptance criteria:**
- [ ] Extracts frames, runs inference, re-encodes
- [ ] Supports DDColor backend (ddcolor_artistic, ddcolor_modelscope)
- [ ] Supports Deoldify backend (Artistic, Stable, Video) as alternative
- [ ] Preserves luminance from original grayscale; only replaces chroma channels (YCbCr)
- [ ] Style selector and saturation slider in settings
- [ ] Respects VRAMManager recommendations

**Verification:**
- [ ] Manual: colorize B&W video with DDColor, verify chroma replacement
- [ ] Manual: colorize B&W video with Deoldify, verify chroma replacement

**Dependencies:** Tasks 2, 4, 7

**Files likely touched:**
- `processors/colorizer.py`

---

#### Task 18: Pipeline chaining in worker (`core/worker.py` update)

**Description:** Update worker to support multi-step pipelines (denoise → upscale → HDR).

**Acceptance criteria:**
- [ ] Worker executes each pipeline step sequentially
- [ ] Intermediate files created for multi-step pipelines
- [ ] Intermediate files cleaned up after successful completion
- [ ] Cancellation works mid-pipeline (cleans intermediates)

**Verification:**
- [ ] Manual: denoise → upscale pipeline produces single output
- [ ] Manual: cancel mid-pipeline, verify cleanup

**Dependencies:** Tasks 9, 15-17

**Files likely touched:**
- `core/worker.py`

---

#### Task 19: Pre-flight dialog (`ui/dialogs/preflight_dialog.py`)

**Description:** Pre-flight check: FFmpeg, models, CUDA, disk space. Download prompt for missing models.

**Acceptance criteria:**
- [ ] Checks FFmpeg on PATH (or configured path)
- [ ] Checks required models exist for every tool in queue
- [ ] Checks CUDA availability (warns if CPU-only for ML tools)
- [ ] Estimates output size vs available disk space
- [ ] Missing models trigger download prompt (QProgressDialog)

**Verification:**
- [ ] Manual: queue ML job with missing model, verify download prompt
- [ ] Manual: queue with no CUDA, verify warning

**Dependencies:** Tasks 3, 15-17

**Files likely touched:**
- `ui/dialogs/__init__.py`
- `ui/dialogs/preflight_dialog.py`

---

#### Checkpoint: Phase 2

- [ ] Upscaler processes real video end-to-end
- [ ] Denoiser removes noise without destroying detail
- [ ] Colorizer preserves luminance, modifies chroma
- [ ] Pipeline chaining works (denoise → upscale)
- [ ] VRAM manager auto-scales batch/tile
- [ ] Pre-flight catches missing models
- [ ] Cancel kills inference, cleans temp, frees CUDA
- [ ] Only 1 ML job at a time

---

### Phase 3: Advanced Tools

**Goal**: HDR converter, audio tools, full tools panel wiring.

#### Task 20: HDR converter (`processors/hdr_converter.py`)

**Description:** SDR→HDR10 via FFmpeg zscale + tonemap filters.

**Acceptance criteria:**
- [ ] Converts SDR to HDR10 using FFmpeg filter chain
- [ ] Settings: target format (HDR10/HLG), peak nits, tonemap algorithm
- [ ] Output verifiable with ffprobe (correct color metadata)

**Verification:**
- [ ] Manual: convert SDR video, verify HDR10 output with ffprobe

**Dependencies:** Task 7

**Files likely touched:**
- `processors/hdr_converter.py`

---

#### Task 21: Vocal remover (`processors/audio/vocal_remover.py`)

**Description:** Demucs stem separation with re-mux.

**Acceptance criteria:**
- [ ] Extracts audio from video via FFmpeg
- [ ] Runs Demucs separation (vocals, drums, bass, other)
- [ ] Re-muxes chosen stems back into video
- [ ] Settings: stem checkboxes, output format, quick/full mode

**Verification:**
- [ ] Manual: separate stems, verify vocal isolation

**Dependencies:** Tasks 2, 7

**Files likely touched:**
- `processors/audio/__init__.py`
- `processors/audio/vocal_remover.py`

---

#### Task 22: Audio upmixer (`processors/audio/upmixer.py`)

**Description:** FFmpeg channel upmix (stereo → 5.1/7.1).

**Acceptance criteria:**
- [ ] Upmixes stereo to 5.1 or 7.1 via FFmpeg channel filters
- [ ] Settings: target layout, bitrate, LFE gain
- [ ] Output verifiable with ffprobe (correct channel layout)

**Verification:**
- [ ] Manual: upmix stereo audio, verify 5.1 output with ffprobe

**Dependencies:** Tasks 2, 7

**Files likely touched:**
- `processors/audio/upmixer.py`

---

#### Task 23: Tools panel (`ui/panels/tools_panel.py`)

**Description:** Tab widget wiring all tools' settings UIs.

**Acceptance criteria:**
- [ ] Tab widget with tabs: Upscaler, Denoiser, Colorizer, HDR, Audio, Convert
- [ ] Each tab shows tool-specific settings (sliders, dropdowns, checkboxes)
- [ ] Settings map to job params dict

**Verification:**
- [ ] Manual: switch tabs, verify settings UI for each tool
- [ ] Manual: set settings, add to queue, verify params passed correctly

**Dependencies:** Tasks 11-13, 20-22

**Files likely touched:**
- `ui/panels/tools_panel.py`

---

#### Checkpoint: Phase 3

- [ ] HDR conversion produces valid HDR10 output
- [ ] Vocal remover isolates stems and re-muxes
- [ ] Audio upmixer produces valid 5.1/7.1 output
- [ ] Tools panel tabs show correct settings UI
- [ ] All tools in pipeline selector for chaining

---

### Phase 4: Polish & Distribution

**Goal**: Settings dialog, model manager, theme customization, packaging.

#### Task 24: Settings dialog (`ui/dialogs/settings_dialog.py`)

**Description:** App settings (theme, FFmpeg path, GPU, concurrent jobs).

**Acceptance criteria:**
- [ ] All config sections editable in dialog
- [ ] Changes persist to TOML on save
- [ ] Runtime theme switching works without restart

**Verification:**
- [ ] Manual: change theme, verify applies without restart
- [ ] Manual: change FFmpeg path, verify persists

**Dependencies:** Task 3

**Files likely touched:**
- `ui/dialogs/settings_dialog.py`

---

#### Task 25: Model manager dialog (`ui/dialogs/model_manager_dialog.py`)

**Description:** Model download manager with status, size, download/delete.

**Acceptance criteria:**
- [ ] Lists all models with status (downloaded/missing)
- [ ] Shows file size and disk usage
- [ ] Download button with QProgressDialog
- [ ] Delete button removes model files
- [ ] SHA256 checksum verification on load

**Verification:**
- [ ] Manual: download a model, verify file and checksum
- [ ] Manual: delete a model, verify removed

**Dependencies:** Task 19

**Files likely touched:**
- `ui/dialogs/model_manager_dialog.py`

---

#### Task 26: Custom widgets (`ui/widgets/`)

**Description:** Collapsible sections, progress bar delegate, drag-and-drop area.

**Acceptance criteria:**
- [ ] `collapsible_section.py`: collapsible UI sections for tool settings
- [ ] `progress_bar_delegate.py`: custom progress bar for queue table
- [ ] `drag_drop_area.py`: drag-and-drop file support on main window

**Verification:**
- [ ] Manual: widgets render and function correctly

**Dependencies:** None (independent widgets)

**Files likely touched:**
- `ui/widgets/__init__.py`
- `ui/widgets/collapsible_section.py`
- `ui/widgets/progress_bar_delegate.py`
- `ui/widgets/drag_drop_area.py`

---

#### Task 27: Theme finalization + PyInstaller spec

**Description:** Final QSS overrides, qtawesome icons, PyInstaller spec file.

**Acceptance criteria:**
- [ ] `custom_overrides.qss` has final styles (log panel, table, progress bar, tabs)
- [ ] qtawesome icons on all buttons
- [ ] PyInstaller spec builds working binary

**Verification:**
- [ ] Manual: PyInstaller builds binary, runs correctly

**Dependencies:** Tasks 24-26

**Files likely touched:**
- `assets/themes/custom_overrides.qss`
- `ui/main_window.py` (icon wiring)
- `videocraft.spec`

---

#### Checkpoint: Phase 4 (Complete)

- [ ] Settings dialog persists all preferences
- [ ] Runtime theme switching works
- [ ] Model manager shows/download/deletes all models
- [ ] Drag-and-drop works on source panel and main window
- [ ] PyInstaller builds working binaries for all 3 platforms
- [ ] Full end-to-end: denoise → upscale → HDR pipeline on real video
- [ ] All acceptance criteria from all phases met

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Real-ESRGAN/SCUNet API changes | High | Pin exact versions in requirements; test with sample video early |
| CUDA OOM on low-VRAM GPUs | High | VRAMManager auto-scales; retry with half batch size; CPU fallback |
| FFmpeg version incompatibilities | Medium | Pin FFmpeg build; test filter chains on target FFmpeg version |
| Demucs model download failures | Medium | Retry logic; manual download fallback; clear error messages |
| PyInstaller bundling ML models | Medium | Exclude models from bundle; download at first run |
| PyQt6 thread safety issues | High | Strict QThread usage; never touch GUI from worker threads |

## Open Questions

- [x] **FFmpeg**: Bundle in `assets/bin/` (platform-specific binaries shipped with the app)
- [x] **Colorization**: Both DDColor and Deoldify — user chooses model backend in settings
- [x] **Model downloads**: Try all 3 sources (HuggingFace → GitHub releases → direct URLs) with fallback
- [x] **Python version**: 3.11 minimum (most compatible across platforms; supports all deps, f-strings, pattern matching)
