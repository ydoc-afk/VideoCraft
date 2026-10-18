"""Job dataclass — core unit of work in the VideoCraft pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Job:
    """Represents a single processing job in the queue.

    Attributes:
        id: Unique UUID4 string.
        source_path: Input file path.
        output_path: Final output file path.
        pipeline: Ordered list of tool names, e.g. ["denoiser", "upscaler"].
        params: Tool-specific settings dict (keys match pipeline order).
        status: Current job status.
        progress: Overall progress 0.0–1.0.
        log_lines: Accumulated log output.
        created_at: Timestamp of job creation.
        cancelled: Atomic cancellation flag checked by worker + processors.
        intermediate_files: Temp files for multi-step pipeline chaining.
    """

    source_path: Path
    output_path: Path
    pipeline: list[str]
    params: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0
    log_lines: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    cancelled: bool = False
    intermediate_files: list[Path] = field(default_factory=list)
