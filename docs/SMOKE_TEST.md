# Smoke test checklist

A hands-on pass to run on a real machine (ideally with an NVIDIA GPU) before a release, and a guide for outside testers. Automated tests cover the logic but have never run the AI models on a GPU or with the real downloaded weights, so that is what this is for.

Mark each line ✅ / ❌ and note anything odd. Two minutes per item is plenty; use short clips (5–10 s) and small photos first, then one larger file to stress memory.

## 0. Record your setup
- [ ] `videocraft --version`, distro, Python version (`python3 --version`)
- [ ] GPU model, VRAM, driver version (`nvidia-smi`)
- [ ] Install method (`./install.sh`, `pipx`, from source)

## 1. Install and self-check
- [ ] `./install.sh` finishes without errors (note the PyTorch download size and time)
- [ ] The setup self-check prints `[ok]` for PyTorch, Upscaler, Denoiser, Colorizer and Vocal remover
- [ ] The PyTorch line names your GPU (`CUDA GPU: …`), **not** "CPU only" — if it says CPU only on a machine with an NVIDIA GPU, that's a bug: report the output of `nvidia-smi` and `videocraft setup --dry-run`
- [ ] `videocraft` opens the app from the terminal and from the app menu (icon shows)
- [ ] `./install.sh --uninstall` removes the app but keeps your config and models (try this last)

## 2. Models
- [ ] Tools → Model Manager lists 7 models with sizes
- [ ] **Download All Missing** works with progress bars (about 2 GB total). Note whether you needed a Hugging Face token
- [ ] After downloading, **Verify Installed** shows `✓ Verified` for every model; hovering a status shows its SHA-256
- [ ] Corrupt one file on purpose (append a byte to a copy in the models folder, or truncate it): Verify shows `✗ Corrupt or modified`; deleting and re-downloading fixes it
- [ ] Settings → General → Hugging Face: **Set up token…** opens the step-by-step window and the links work (you don't have to save a token)

## 3. Photos
Use a JPG, a PNG, a WebP, a photo with an **odd size** (e.g. 1001×667), a **phone photo** (EXIF rotation), and a PNG with **transparency**.
- [ ] Drag-and-drop and File → Open accept photos; the Source panel shows a thumbnail and metadata
- [ ] Upscaler ×2 and ×4 on a photo: output is exactly 2× / 4× the pixels, same format, saved as `<name>_output.<ext>`, and looks sharper without obvious artifacts
- [ ] Denoiser on a noisy photo: noise reduced, detail kept
- [ ] Colorizer on a black-and-white photo: plausible colours; try **Artistic** and **ModelScope**, and the saturation setting
- [ ] Phone photo comes out the **right way up** (known untested: report if rotated)
- [ ] Transparent PNG: note what happens to the transparency (known untested)
- [ ] A photo queued with the Convert / HDR / Audio tab is skipped with a clear log message

## 4. Video (AI tools)
- [ ] Upscaler ×2 on a short clip: output resolution doubled, audio kept, plays correctly, frame rate unchanged
- [ ] Upscaler anime model on an animation clip
- [ ] Denoiser on a noisy clip
- [ ] Colorizer on a short black-and-white clip: colours appear. **Expected:** some colour flicker on moving scenes (each frame is coloured separately) — note how bad
- [ ] A clip with an **odd width/height** (e.g. 853×479) processes without an encode error
- [ ] Watch the GPU (`nvidia-smi -l 1`): memory is used while running and freed afterwards
- [ ] A larger/longer clip (e.g. 1080p, 1 minute) with **Tile size: Auto** completes without a CUDA out-of-memory error; if it fails, note the file size, GPU and the log text
- [ ] Settings → GPU device = **cpu** really uses the CPU (no GPU memory use; much slower)

## 5. Video and audio tools (no AI)
- [ ] Convert: MP4 → MKV, MP4 → WebM, MP4 → GIF all play; the CRF presets (Fast / Balanced / Quality) change size and quality
- [ ] Convert with **Copy** video codec finishes instantly
- [ ] HDR: SDR clip → HDR10 output plays as HDR in a capable player (or at least has BT.2020 metadata: `ffprobe`)
- [ ] Audio upmix: stereo → 5.1 plays with all channels
- [ ] Vocal remover on a song: first run downloads Demucs weights (note time); the output has no (or much quieter) vocals; try WAV, FLAC and an MP3 output

## 6. Queue and cancelling
- [ ] Queue 3+ files, **Start Queue**: the pre-flight window appears (CUDA / models / disk checks), jobs run one ML job at a time
- [ ] A converter job queued behind a running ML job is not blocked when Settings → Concurrent jobs is 2 or more
- [ ] **Cancel** a running job during extraction, during processing, and during the final encode: it stops within a few seconds and leaves no temp files behind
- [ ] **Pause** lets the running job finish and starts nothing new; Start resumes
- [ ] Running a job whose output already exists keeps the old file as `<name>_output_<timestamp>.<ext>`
- [ ] Close the window while a job is running: it shuts down cleanly (no crash or hang)

## 7. Settings
- [ ] Changing the theme applies immediately
- [ ] A custom FFmpeg path (Settings → FFmpeg) is used; clearing it goes back to the one on your PATH
- [ ] Saved defaults (upscaler scale/model, colorizer, HDR nits) show up in the Tools tabs

## What to send back
For each ❌ or odd result: the item number, your setup from section 0, what you expected, what happened, and the log panel text (Log panel → copy) plus the file type/size/resolution of the input. Report at <https://github.com/ydoc-afk/VideoCraft/issues>.

## Known limitations (don't report these)
- Colorizer colours can flicker on moving footage.
- Linux only for now; AMD GPUs are untested.
- The AI tools need Python 3.11 or 3.12 (basicsr does not build on 3.13).
