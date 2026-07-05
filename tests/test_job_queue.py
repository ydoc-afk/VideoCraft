"""Tests for core.job_queue — thread-safe queue manager."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from core.job import Job
from core.job_queue import JobQueue


def test_queue_add_and_order():
    """Jobs are added to the queue in order."""
    q = JobQueue()
    j1 = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    j2 = Job(source_path=Path("/tmp/b.mp4"), output_path=Path("/tmp/b_out.mp4"), pipeline=["converter"])
    j3 = Job(source_path=Path("/tmp/c.mp4"), output_path=Path("/tmp/c_out.mp4"), pipeline=["converter"])

    q.add(j1)
    q.add(j2)
    q.add(j3)

    assert len(q.jobs) == 3
    assert q.jobs[0] is j1
    assert q.jobs[1] is j2
    assert q.jobs[2] is j3


def test_queue_cancel():
    """Cancelling a job sets its cancelled flag and status."""
    q = JobQueue()
    j = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    q.add(j)

    q.cancel(j.id)

    assert j.cancelled is True
    assert j.status == "cancelled"


def test_queue_cancel_unknown_id():
    """Cancelling an unknown job ID is a no-op."""
    q = JobQueue()
    q.cancel("nonexistent-id")  # should not raise


def test_queue_remove():
    """Removing a job takes it out of the queue."""
    q = JobQueue()
    j1 = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    j2 = Job(source_path=Path("/tmp/b.mp4"), output_path=Path("/tmp/b_out.mp4"), pipeline=["converter"])
    q.add(j1)
    q.add(j2)

    q.remove(j1.id)

    assert len(q.jobs) == 1
    assert q.jobs[0] is j2


def test_queue_clear_completed():
    """Clear completed removes done/cancelled jobs."""
    q = JobQueue()
    j1 = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    j2 = Job(source_path=Path("/tmp/b.mp4"), output_path=Path("/tmp/b_out.mp4"), pipeline=["converter"])
    j3 = Job(source_path=Path("/tmp/c.mp4"), output_path=Path("/tmp/c_out.mp4"), pipeline=["converter"])
    j1.status = "done"
    j2.status = "running"
    j3.status = "cancelled"
    q.add(j1)
    q.add(j2)
    q.add(j3)

    q.clear_completed()

    assert len(q.jobs) == 1
    assert q.jobs[0] is j2


def test_queue_is_ml_tool():
    """ML tools are correctly identified."""
    q = JobQueue()
    assert q._is_ml_tool("converter") is False
    assert q._is_ml_tool("upscaler") is True
    assert q._is_ml_tool("denoiser") is True
    assert q._is_ml_tool("colorizer") is True
    assert q._is_ml_tool("vocal_remover") is True


def test_queue_next_available():
    """next_available returns the first queued job."""
    q = JobQueue()
    j1 = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    j2 = Job(source_path=Path("/tmp/b.mp4"), output_path=Path("/tmp/b_out.mp4"), pipeline=["converter"])
    j1.status = "running"
    q.add(j1)
    q.add(j2)

    next_job = q.next_available()
    assert next_job is j2


def test_queue_next_available_none():
    """next_available returns None when no queued jobs."""
    q = JobQueue()
    j = Job(source_path=Path("/tmp/a.mp4"), output_path=Path("/tmp/a_out.mp4"), pipeline=["converter"])
    j.status = "running"
    q.add(j)

    assert q.next_available() is None
