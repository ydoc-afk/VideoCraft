"""Tests for core.job — Job dataclass."""

from core.job import Job
from pathlib import Path
import uuid


def test_job_defaults():
    """Job created with minimal args gets correct defaults."""
    job = Job(
        source_path=Path("/tmp/input.mp4"),
        output_path=Path("/tmp/output.mp4"),
        pipeline=["converter"],
    )

    # ID is a valid UUID string
    uuid.UUID(job.id, version=4)
    assert job.status == "queued"
    assert job.progress == 0.0
    assert job.log_lines == []
    assert job.cancelled is False
    assert job.intermediate_files == []
    assert job.created_at is not None


def test_job_explicit_values():
    """Job respects explicit field values."""
    job = Job(
        source_path=Path("/tmp/a.mp4"),
        output_path=Path("/tmp/b.mp4"),
        pipeline=["denoiser", "upscaler"],
        params={"denoiser": {"noise_level": 25}},
        status="running",
        progress=0.5,
    )

    assert len(job.pipeline) == 2
    assert job.pipeline[0] == "denoiser"
    assert job.pipeline[1] == "upscaler"
    assert job.params == {"denoiser": {"noise_level": 25}}
    assert job.status == "running"
    assert job.progress == 0.5


def test_job_cancel_flag():
    """Cancelled flag can be toggled."""
    job = Job(
        source_path=Path("/tmp/x.mp4"),
        output_path=Path("/tmp/y.mp4"),
        pipeline=["converter"],
    )
    assert job.cancelled is False
    job.cancelled = True
    assert job.cancelled is True


def test_job_intermediate_files():
    """Intermediate files list can be appended to."""
    job = Job(
        source_path=Path("/tmp/x.mp4"),
        output_path=Path("/tmp/y.mp4"),
        pipeline=["denoiser", "upscaler"],
    )
    job.intermediate_files.append(Path("/tmp/step0_denoiser.mp4"))
    assert len(job.intermediate_files) == 1
    assert job.intermediate_files[0] == Path("/tmp/step0_denoiser.mp4")
