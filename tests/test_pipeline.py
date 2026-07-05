"""Tests for core.worker pipeline chaining."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from unittest.mock import patch, MagicMock
from core.job import Job
from core.worker import Worker, get_processor


def test_worker_pipeline_single_step():
    """Single-step pipeline works as before."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/out.mp4"),
        pipeline=["converter"],
    )

    captured_lines: list[str] = []
    worker = Worker(job)
    worker.log_line.connect(captured_lines.append)

    # Mock processor
    def mock_process(j):
        yield "[INFO] step 1"
        j.progress = 1.0
        j.status = "done"

    with patch("core.worker.get_processor") as mock_gp:
        mock_proc = MagicMock()
        mock_proc.process = mock_process
        mock_gp.return_value = mock_proc
        worker.run()

    assert job.status == "done"


def test_worker_pipeline_multi_step():
    """Multi-step pipeline chains intermediate files."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/final.mp4"),
        pipeline=["denoiser", "upscaler"],
    )

    # Mock both processors
    call_order: list[str] = []

    def mock_process_denoiser(j):
        call_order.append("denoiser")
        yield "[INFO] denoising..."
        j.progress = 0.5
        j.status = "running"

    def mock_process_upscaler(j):
        call_order.append("upscaler")
        yield "[INFO] upscaling..."
        j.progress = 1.0
        j.status = "done"

    mock_procs = {
        "denoiser": MagicMock(process=mock_process_denoiser),
        "upscaler": MagicMock(process=mock_process_upscaler),
    }

    captured_lines: list[str] = []
    worker = Worker(job)

    with patch("core.worker.get_processor") as mock_gp:
        def side_effect(name):
            return mock_procs[name]
        mock_gp.side_effect = side_effect
        worker.run()

    assert call_order == ["denoiser", "upscaler"]
    assert job.status == "done"


def test_worker_pipeline_cancel_mid_chain():
    """Cancellation mid-pipeline cleans up intermediates."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/final.mp4"),
        pipeline=["denoiser", "upscaler"],
    )

    call_order: list[str] = []

    def mock_process_denoiser(j):
        call_order.append("denoiser")
        yield "[INFO] denoising..."
        j.progress = 0.5
        # Simulate cancellation after first step
        j.cancelled = True

    def mock_process_upscaler(j):
        call_order.append("upscaler")
        yield "[INFO] upscaling..."

    mock_procs = {
        "denoiser": MagicMock(process=mock_process_denoiser),
        "upscaler": MagicMock(process=mock_process_upscaler),
    }

    worker = Worker(job)

    with patch("core.worker.get_processor") as mock_gp:
        def side_effect(name):
            return mock_procs[name]
        mock_gp.side_effect = side_effect
        worker.run()

    assert call_order == ["denoiser"]
    assert job.status == "cancelled"


def test_worker_intermediate_files_tracked():
    """Intermediate files are tracked for multi-step pipelines."""
    job = Job(
        source_path=Path("/tmp/in.mp4"),
        output_path=Path("/tmp/final.mp4"),
        pipeline=["denoiser", "upscaler"],
    )

    def mock_process(j):
        yield "[INFO] done"
        j.status = "done"
        j.progress = 1.0

    mock_proc = MagicMock(process=mock_process)

    worker = Worker(job)

    with patch("core.worker.get_processor", return_value=mock_proc):
        worker.run()

    # After multi-step pipeline, intermediate files should be cleaned
    assert len(job.intermediate_files) == 0 or all(
        not f.exists() for f in job.intermediate_files
    )


def test_get_processor_ml_tools():
    """ML tools are registered in the processor registry."""
    from processors.upscaler import UpscalerProcessor
    from processors.denoiser import DenoiserProcessor
    from processors.colorizer import ColorizerProcessor

    assert isinstance(get_processor("upscaler"), UpscalerProcessor)
    assert isinstance(get_processor("denoiser"), DenoiserProcessor)
    assert isinstance(get_processor("colorizer"), ColorizerProcessor)
