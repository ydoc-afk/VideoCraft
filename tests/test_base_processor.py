"""Tests for processors.base_processor — abstract base class."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.base_processor import BaseProcessor
from core.job import Job
from pathlib import Path


def test_base_processor_is_abstract():
    """BaseProcessor cannot be instantiated directly."""
    try:
        BaseProcessor()
        assert False, "Should not be able to instantiate BaseProcessor"
    except TypeError:
        pass  # Expected


def test_concrete_processor_implements_process():
    """A concrete subclass can implement process()."""
    class DummyProcessor(BaseProcessor):
        def process(self, job: Job):
            yield "[INFO] dummy processing"
            job.progress = 1.0
            yield "[SUCCESS] done"

    proc = DummyProcessor()
    job = Job(source_path=Path("/tmp/in.mp4"), output_path=Path("/tmp/out.mp4"), pipeline=["dummy"])
    lines = list(proc.process(job))
    assert len(lines) == 2
    assert "dummy processing" in lines[0]
    assert job.progress == 1.0


def test_processor_checks_cancellation():
    """Processor stops early when job.cancelled is True."""
    class CancellingProcessor(BaseProcessor):
        def process(self, job: Job):
            yield "[INFO] step 1"
            if job.cancelled:
                yield "[INFO] cancelled"
                return
            yield "[INFO] step 2"

    proc = CancellingProcessor()
    job = Job(source_path=Path("/tmp/in.mp4"), output_path=Path("/tmp/out.mp4"), pipeline=["dummy"])
    job.cancelled = True
    lines = list(proc.process(job))
    assert "step 1" in lines[0]
    assert "cancelled" in lines[1]
    assert len(lines) == 2  # step 2 was skipped
