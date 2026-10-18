# Changelog

All notable changes to VideoCraft are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- **Multi-step pipelines** (e.g. denoise → upscale) re-processed the original
  file at every step, discarding earlier results. Each step now reads the
  previous step's output, and source/output paths are restored after a
  cancel or failure.
- **Cancelling a running job** freed its concurrency slot immediately, so the
  next ML job could start while the first still held the GPU. The slot is now
  held until the worker thread exits.
- **Cancel and window close** no longer wait out long steps: frame extraction,
  the final re-encode and the vocal remover's FFmpeg/Demucs steps are
  cancellable, and shutdown waits up to 15 s per worker.
- **Frame-based tools** failed to re-encode sources with an odd width or
  height; frames are now padded to even dimensions.
- **Converter progress** barely updated (FFmpeg's carriage-return status
  lines were never split) and cancellation lagged; progress now updates
  continuously.
- **WebM output** failed with the default H.264/AAC settings; WebM now uses
  VP9 + Opus.
- **Vocal remover** picked the audio encoder from the format setting instead
  of the output extension (so `.mp3`/`.ogg` outputs could fail) and failed
  on audio-only sources when remuxing.
- **Existing output files** were silently overwritten by the frame-based
  tools and the vocal remover; they are now backed up with a timestamp, like
  the converter, HDR and upmixer already did.
- **Queue** no longer lets a waiting ML job block later jobs that could run,
  and Start Queue runs pre-flight checks for every distinct queued ML setup,
  not just the first.
- **Settings** for concurrent jobs and the FFmpeg path now apply immediately
  instead of after a restart; clearing the FFmpeg path restores the detected
  binary.
- Source panel no longer adds the same file twice.

### Changed
- The **Convert tab** is now the single place for converter settings
  (container, codecs, CRF and the Fast/Balanced/Quality presets). The Output
  panel only chooses the destination folder.
- **Settings now take effect**: GPU device (including forcing CPU), FFmpeg
  thread count, and the saved defaults for the upscaler (scale, model, tile
  size), colorizer and HDR peak brightness now seed the Tools panel.
- The Settings default-scale control is limited to 2x and 4x.

### Removed
- Denoiser noise-level slider and artifact-removal checkbox, and the HDR
  tonemap choice (including `hdr.tonemap` in the config). No processor used
  them. Existing config files that still contain `tonemap` load normally.

### Added
- GPL-3.0 license and third-party notices.
- GitHub Actions workflow that runs the test suite on every push and pull
  request.
- **Installable package**: `pip`/`pipx` installable, with a `videocraft`
  command, `python -m videocraft`, and an `ml` extra for the AI packages.
- **`videocraft setup`**: detects an NVIDIA GPU and its driver's CUDA version,
  installs the matching PyTorch build plus the other AI packages, applies a
  fix for basicsr's torchvision import, and checks that each tool works.
- **`install.sh`** (Linux): private environment, `videocraft` command,
  app-menu entry, and the AI tools in one step; `--uninstall` included.
- Release workflow: pushing a `v*` tag runs the tests, builds the source and
  wheel packages and publishes a GitHub release.
- README: project status, install instructions, and release steps.

- **Hugging Face token help**: when a model download is refused (HTTP
  401/403/429) a window explains step by step how to create a free token,
  tests it, saves it (owner-only file, sent only to huggingface.co) and
  retries. Also available under Settings → Hugging Face, or via `HF_TOKEN`.

- **Photo support**: the Upscaler, Denoiser and Colorizer accept JPG, PNG,
  WebP, BMP and TIFF images and write the result in the same format. Other
  tools skip photos with a log message. Supported file types now live in one
  place (`videocraft/core/media.py`).
- **Working colorizer**: DDColor's inference code is now vendored
  (Apache-2.0, `processors/archs/ddcolor/`), so the colorizer runs with just
  PyTorch and OpenCV. `videocraft setup` checks it.

### Removed (colorizer)
- DeOldify support and its three model downloads: its dependencies are
  unreliable on current Python. `colorizer.backend` is gone from the config
  (old files that still contain it load normally).

- **Model checksums**: every model's SHA-256 is pinned. Downloads that don't
  match are discarded with a clear error, and the Model Manager has a
  **Verify Installed** button (shows each file's hash on hover). A "Model
  hashes" workflow and `scripts/compute_model_hashes.py` regenerate the values
  when an upstream file changes.

### Changed (packaging)
- Code now lives in the `videocraft` package (`videocraft.core`,
  `videocraft.processors`, `videocraft.ui`); `requirements.txt` is replaced by
  `pyproject.toml`. The version is defined once in `videocraft/__init__.py`.
- Downloaded models are stored in the per-user data folder
  (`~/.local/share/videocraft/models`, or `$VIDEOCRAFT_MODELS_DIR`) instead of
  next to the code.

## Known limitations
- The **colorizer** (DDColor) colorizes each frame independently, so colours
  can flicker on moving footage; it has not been tested with real weights on a
  GPU yet.
- Model downloads and a single frame's inference cannot be interrupted
  mid-call.
- Linux only for now; a Windows installer is planned. AMD GPUs (ROCm) are
  untested (`videocraft setup --torch-index-url` can point at a ROCm build).
- The AI tools need Python 3.11 or 3.12: the Real-ESRGAN dependency `basicsr`
  does not build on Python 3.13.
