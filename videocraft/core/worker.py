"""QThread worker — runs a job's pipeline and emits signals."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from videocraft.core.job import Job
from videocraft.processors.base_processor import BaseProcessor
from videocraft.processors.converter import ConverterProcessor
from videocraft.processors.upscaler import UpscalerProcessor
from videocraft.processors.denoiser import DenoiserProcessor
from videocraft.processors.colorizer import ColorizerProcessor
from videocraft.processors.hdr_converter import HDRConverterProcessor
from videocraft.processors.audio.vocal_remover import VocalRemoverProcessor
from videocraft.processors.audio.upmixer import AudioUpmixerProcessor

logger = logging.getLogger(__name__)

# Registry of tool name → processor class
_PROCESSORS: dict[str, type[BaseProcessor]] = {
    "converter": ConverterProcessor,
    "upscaler": UpscalerProcessor,
    "denoiser": DenoiserProcessor,
    "colorizer": ColorizerProcessor,
    "hdr": HDRConverterProcessor,
    "vocal_remover": VocalRemoverProcessor,
    "upmixer": AudioUpmixerProcessor,
}


def get_processor(tool_name: str) -> BaseProcessor:
    """Look up and instantiate a processor by tool name."""
    cls = _PROCESSORS.get(tool_name)
    if cls is None:
        raise ValueError(f"Unknown tool: {tool_name} (available: {list(_PROCESSORS.keys())})")
    return cls()


def register_processor(tool_name: str, processor_cls: type[BaseProcessor]) -> None:
    """Register a processor class for a tool name."""
    _PROCESSORS[tool_name] = processor_cls


class Worker(QThread):
    """Worker thread that runs a job's pipeline.

    Supports multi-step pipelines (e.g., denoise → upscale → colorize).
    Each step's output becomes the next step's input via intermediate files.

    Signals:
        log_line: Emitted for each log line from the processor.
        progress: Emitted when job progress changes.
        job_done: Emitted when job completes successfully.
        job_failed: Emitted when job fails with an error message.
    """

    log_line = pyqtSignal(str)
    progress = pyqtSignal(float)
    job_done = pyqtSignal(object)
    job_failed = pyqtSignal(object, str)

    def __init__(self, job: Job) -> None:
        super().__init__()
        self.job = job
        self._temp_dirs: list[Path] = []

    def run(self) -> None:
        """Execute the job's pipeline (single or multi-step)."""
        self.job.status = "running"
        pipeline = self.job.pipeline
        # Processors read job.source_path / job.output_path, so chaining
        # works by swapping them per step; restore both when we're done.
        original_source = self.job.source_path
        original_output = self.job.output_path

        try:
            total_steps = len(pipeline)
            last_error = ""

            for step_idx, tool_name in enumerate(pipeline):
                if self.job.cancelled:
                    self.job.status = "cancelled"
                    self.log_line.emit("[CANCELLED] Job cancelled by user")
                    return

                step_num = step_idx + 1
                self.log_line.emit(
                    f"[INFO] Step {step_num}/{total_steps}: {tool_name}"
                )

                # Previous step's output is this step's input
                if step_idx > 0 and self.job.intermediate_files:
                    self.job.source_path = self.job.intermediate_files[-1]
                self.job.progress = 0.0

                processor = get_processor(tool_name)

                # Set up intermediate output for multi-step
                if step_idx < total_steps - 1:
                    temp_dir = Path(tempfile.mkdtemp(prefix=f"videocraft_step{step_idx}_"))
                    self._temp_dirs.append(temp_dir)
                    intermediate_name = f"step{step_idx}_output{self.job.output_path.suffix}"
                    step_output = temp_dir / intermediate_name
                    self.job.intermediate_files.append(step_output)
                    # Temporarily swap output for this step
                    self.job.output_path = step_output
                else:
                    self.job.output_path = original_output

                # Run the processor. The processor is the sole writer of
                # job.progress (its own per-step 0.0–1.0 value); the worker
                # only *reads* it to emit an overall figure. Writing the
                # scaled value back would feed it into the next read and
                # send progress backwards.
                for line in processor.process(self.job):
                    if self.job.cancelled:
                        self.job.status = "cancelled"
                        self.log_line.emit("[CANCELLED] Job cancelled by user")
                        return
                    self.log_line.emit(line)
                    if line.startswith("[ERROR]"):
                        last_error = line.removeprefix("[ERROR]").strip()

                    step_progress = min(max(self.job.progress, 0.0), 1.0)
                    overall = (step_idx + step_progress) / total_steps
                    if overall > 0:
                        self.progress.emit(overall)

                # Processors report failure by setting job.status (they
                # yield log lines rather than raising) — honor it.
                if self.job.status == "failed":
                    self.job_failed.emit(self.job, last_error or f"{tool_name} failed")
                    return

            self.job.status = "done"
            self.job.progress = 1.0
            self.progress.emit(1.0)
            self.job_done.emit(self.job)

        except Exception as e:
            self.job.status = "failed"
            self.job_failed.emit(self.job, str(e))
            logger.error("Job %s failed: %s", self.job.id, e, exc_info=True)
        finally:
            self.job.source_path = original_source
            self.job.output_path = original_output
            self._cleanup_temps()
            # Clean intermediate files
            self._cleanup_intermediates()

    def _cleanup_temps(self) -> None:
        """Clean up any temp directories created during processing."""
        for d in self._temp_dirs:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                logger.debug("Cleaned temp dir: %s", d)
        self._temp_dirs.clear()

    def _cleanup_intermediates(self) -> None:
        """Clean up intermediate files from multi-step pipelines."""
        for f in self.job.intermediate_files:
            try:
                if f.is_dir():
                    shutil.rmtree(f, ignore_errors=True)
                else:
                    f.unlink(missing_ok=True)
                logger.debug("Cleaned intermediate: %s", f)
            except OSError as e:
                logger.warning("Could not clean intermediate %s: %s", f, e)
        self.job.intermediate_files.clear()

    def register_temp_dir(self, path: Path) -> None:
        """Track a temp directory for cleanup."""
        self._temp_dirs.append(path)
