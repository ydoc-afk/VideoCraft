"""Vocal remover — Demucs stem separation with re-mux."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from core.ffmpeg import ffmpeg_cmd
from core.job import Job
from processors.base_processor import BaseProcessor
from processors.converter import ffprobe_duration

logger = logging.getLogger(__name__)

# Available stems from Demucs
_ALL_STEMS = ["vocals", "drums", "bass", "other"]

# Output formats for the final audio
_AUDIO_FORMATS = {
    "wav": {"codec": "pcm_s16le", "bitrate": None},
    "flac": {"codec": "flac", "bitrate": None},
    "aac": {"codec": "aac", "bitrate": "192k"},
}


class VocalRemoverProcessor(BaseProcessor):
    """Demucs stem separation processor.

    Pipeline:
    1. Extract audio from video via FFmpeg
    2. Run Demucs separation (Demucs downloads its own weights on first run)
    3. Re-mux chosen stems back into video (or output audio-only)

    Settings:
        stems: list of stem names to keep (default: all except vocals)
        output_format: "wav" | "flac" | "aac" (default: "wav")
        mode: "remove_vocals" | "full_separation" (default: "remove_vocals")
        model: "htdemucs_ft" | "htdemucs" | "hdemucs" (default: "htdemucs_ft")
    """

    def __init__(self) -> None:
        self._temp_dir: Path | None = None

    def process(self, job: Job):
        """Run vocal removal / stem separation, yielding log lines."""
        if job.cancelled:
            yield "[INFO] Job cancelled by user"
            return

        params = job.params
        # Default to the tool's namesake behavior: remove vocals.
        stems = params.get("stems") or [s for s in _ALL_STEMS if s != "vocals"]
        output_format = params.get("output_format", "wav")
        mode = params.get("mode", "remove_vocals")
        model = params.get("model", "htdemucs_ft")

        # "Remove Vocals" quick mode: keep everything except vocals
        if mode == "remove_vocals":
            stems = [s for s in _ALL_STEMS if s != "vocals"]

        duration = ffprobe_duration(job.source_path) or 0.0

        yield f"[INFO] Starting vocal removal: {job.source_path.name}"
        yield f"[INFO] Model: {model}, Mode: {mode}, Stems: {stems}"

        # Temp dir is cleaned up in _cleanup(); job.intermediate_files is
        # reserved for step-output files the worker chains and unlinks.
        self._temp_dir = Path(tempfile.mkdtemp(prefix="videocraft_audio_"))

        wav_path = self._temp_dir / "audio_extract.wav"
        stems_dir = self._temp_dir / "stems"

        try:
            # Step 1: Extract audio
            yield "[INFO] Extracting audio track..."
            job.progress = 0.1
            if not self._extract_audio(job.source_path, wav_path, duration):
                yield "[ERROR] Failed to extract audio"
                job.status = "failed"
                return

            if job.cancelled:
                yield "[INFO] Job cancelled by user"
                return

            # Step 2: Run Demucs separation
            yield "[INFO] Running Demucs stem separation..."
            job.progress = 0.2
            if not self._run_demucs(wav_path, stems_dir, model, duration):
                yield "[ERROR] Demucs separation failed"
                job.status = "failed"
                return

            if job.cancelled:
                yield "[INFO] Job cancelled by user"
                return

            # Step 3: Mix selected stems
            yield f"[INFO] Mixing stems: {stems}"
            job.progress = 0.5
            mixed_path = self._temp_dir / "mixed.wav"
            if not self._mix_stems(stems_dir, stems, mixed_path):
                yield "[ERROR] Failed to mix stems"
                job.status = "failed"
                return

            if job.cancelled:
                yield "[INFO] Job cancelled by user"
                return

            # Step 4: Output — re-mux into video or audio-only
            yield "[INFO] Creating output..."
            job.progress = 0.8
            fmt_info = _AUDIO_FORMATS.get(output_format, _AUDIO_FORMATS["wav"])

            output_ext = job.output_path.suffix.lower()
            audio_exts = {".mp3", ".aac", ".flac", ".wav", ".ogg", ".m4a"}

            ok = True
            if output_ext in audio_exts:
                # Audio-only output
                if output_ext == ".wav":
                    shutil.copy2(mixed_path, job.output_path)
                else:
                    ok = self._encode_audio(mixed_path, job.output_path, fmt_info)
            else:
                # Re-mux into video
                ok = self._remux_audio(job.source_path, mixed_path, job.output_path, duration)

            if not ok:
                yield "[ERROR] Failed to write output"
                job.status = "failed"
                return

            job.progress = 1.0
            yield f"[SUCCESS] Vocal removal complete: {job.output_path.name}"

        except Exception as e:
            yield f"[ERROR] Vocal removal failed: {e}"
            job.status = "failed"
        finally:
            self._cleanup()

    def _extract_audio(self, source: Path, output: Path, duration: float = 0.0) -> bool:
        """Extract audio from video as WAV."""
        cmd = [
            ffmpeg_cmd(), "-y", "-i", str(source),
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(output),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=max(120.0, duration * 5)
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Audio extraction timed out")
            return False

    def _run_demucs(
        self, audio_path: Path, output_dir: Path, model: str, duration: float = 0.0
    ) -> bool:
        """Run Demucs stem separation via the current Python interpreter."""
        cmd = [
            sys.executable, "-m", "demucs.separate",
            "-o", str(output_dir),
            "-n", model,
            str(audio_path),
        ]
        try:
            logger.info("Running Demucs: %s", " ".join(cmd[:6]))
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=max(600.0, duration * 20),
            )
            if result.returncode != 0:
                logger.error("Demucs failed: %s", result.stderr[-800:])
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("Demucs timed out")
            return False
        except FileNotFoundError:
            logger.error("Demucs not found — install with: pip install demucs")
            return False

    def _find_stem_dir(self, stems_dir: Path) -> Path | None:
        """Locate the directory holding <stem>.wav files.

        Demucs writes to <output_dir>/<model_name>/<track_name>/<stem>.wav —
        search rather than assume the depth.
        """
        for stem_name in _ALL_STEMS:
            hit = next(stems_dir.rglob(f"{stem_name}.wav"), None)
            if hit is not None:
                return hit.parent
        return None

    def _mix_stems(self, stems_dir: Path, stems: list[str], output: Path) -> bool:
        """Mix selected stems together using FFmpeg."""
        stem_dir = self._find_stem_dir(stems_dir)
        if stem_dir is None:
            logger.error("No stem files found under %s", stems_dir)
            return False

        stem_files = []
        for stem_name in stems:
            stem_file = stem_dir / f"{stem_name}.wav"
            if stem_file.exists():
                stem_files.append(stem_file)
            else:
                logger.warning("Stem file not found: %s", stem_file)

        if not stem_files:
            logger.error("No valid stem files found")
            return False

        if len(stem_files) == 1:
            # Single stem — just copy
            result = subprocess.run(
                [ffmpeg_cmd(), "-y", "-i", str(stem_files[0]), "-acodec", "copy", str(output)],
                capture_output=True, timeout=120,
            )
            return result.returncode == 0

        # Multiple stems — mix with amix. Stems are complementary parts of
        # one mix, so disable amix's per-input normalization to preserve
        # the original levels.
        inputs = []
        labels = []
        for i, sf in enumerate(stem_files):
            inputs.extend(["-i", str(sf)])
            labels.append(f"[{i}:a]")

        amix_filter = (
            "".join(labels)
            + f"amix=inputs={len(stem_files)}:duration=longest:normalize=0[mix]"
        )

        cmd = [ffmpeg_cmd(), "-y"] + inputs + [
            "-filter_complex", amix_filter,
            "-map", "[mix]",
            "-c:a", "pcm_s16le",
            str(output),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error("Stem mix failed: %s", result.stderr[-500:])
                return False
            return True
        except subprocess.TimeoutExpired:
            return False

    def _encode_audio(self, input_path: Path, output_path: Path, fmt_info: dict) -> bool:
        """Encode audio to target format."""
        cmd = [ffmpeg_cmd(), "-y", "-i", str(input_path)]
        codec = fmt_info.get("codec")
        bitrate = fmt_info.get("bitrate")
        if codec:
            cmd.extend(["-c:a", codec])
        if bitrate:
            cmd.extend(["-b:a", bitrate])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    def _remux_audio(
        self, video_source: Path, audio_source: Path, output: Path, duration: float = 0.0
    ) -> bool:
        """Re-mux processed audio back into the video (copy video, replace audio)."""
        cmd = [
            ffmpeg_cmd(), "-y",
            "-i", str(video_source),
            "-i", str(audio_source),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v",   # video from the source
            "-map", "1:a:0", # processed audio
            "-shortest",
            str(output),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=max(300.0, duration * 10)
            )
            if result.returncode != 0:
                logger.error("Remux failed: %s", result.stderr[-500:])
                return False
            return True
        except subprocess.TimeoutExpired:
            return False

    def _cleanup(self) -> None:
        """Clean up temp directory."""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
