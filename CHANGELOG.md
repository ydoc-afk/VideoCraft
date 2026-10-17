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
- Release workflow: pushing a `v*` tag runs the tests, builds the Linux
  AppImage (with a bundled static FFmpeg) and publishes a GitHub release.
- README: project status, AppImage download instructions, and release steps.

## Known limitations
- The **colorizer** passes frames through unchanged: the DDColor and Deoldify
  inference packages are not available on PyPI yet.
- Model downloads are not checksum-verified yet.
- Model downloads and a single frame's inference cannot be interrupted
  mid-call.
- The AppImage does not include PyTorch or the other ML packages, so the AI
  tools only pass input through there; run from source to use them.
- Only a Linux AppImage build is set up; it has not been published yet.
