"""Thread-safe job queue manager."""

from __future__ import annotations

import logging
import threading
from core.job import Job

logger = logging.getLogger(__name__)

# Tools that require GPU/ML inference — only 1 concurrent instance allowed
_ML_TOOLS = {"upscaler", "denoiser", "colorizer", "vocal_remover"}


def is_ml_job(job: Job) -> bool:
    """True if any step of the job's pipeline needs ML inference."""
    return any(t in _ML_TOOLS for t in job.pipeline)


class JobQueue:
    """Thread-safe queue for managing processing jobs.

    Enforces:
    - Hard limit of 1 concurrent ML job
    - CPU-only jobs can run concurrently if concurrent_jobs > 1
    """

    def __init__(self, concurrent_jobs: int = 1) -> None:
        self.jobs: list[Job] = []
        self.concurrent_jobs = concurrent_jobs
        self._lock = threading.Lock()

    def add(self, job: Job) -> None:
        """Add a job to the end of the queue."""
        with self._lock:
            self.jobs.append(job)
            logger.info("Job added: %s (%s)", job.source_path.name, job.pipeline)

    def cancel(self, job_id: str) -> None:
        """Cancel a job by ID. Jobs that already finished are left untouched."""
        with self._lock:
            for job in self.jobs:
                if job.id == job_id:
                    if job.status in ("done", "failed", "cancelled"):
                        logger.info("Cancel ignored for finished job: %s", job_id)
                        return
                    job.cancelled = True
                    job.status = "cancelled"
                    logger.info("Job cancelled: %s", job_id)
                    return
            logger.warning("Cancel requested for unknown job: %s", job_id)

    def remove(self, job_id: str) -> None:
        """Remove a job from the queue by ID."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.id != job_id]

    def clear_completed(self) -> None:
        """Remove all done/cancelled/failed jobs."""
        with self._lock:
            before = len(self.jobs)
            self.jobs = [j for j in self.jobs if j.status not in ("done", "cancelled", "failed")]
            after = len(self.jobs)
            if before != after:
                logger.info("Cleared %d completed jobs (%d remaining)", before - after, after)

    def next_available(self) -> Job | None:
        """Return the next job with status 'queued', or None."""
        with self._lock:
            for job in self.jobs:
                if job.status == "queued":
                    return job
        return None

    def running_count(self) -> int:
        """Count jobs currently running."""
        with self._lock:
            return sum(1 for j in self.jobs if j.status == "running")

    def ml_running(self) -> bool:
        """Check if any ML job is currently running."""
        with self._lock:
            for j in self.jobs:
                if j.status == "running" and is_ml_job(j):
                    return True
        return False

    def can_start(self, job: Job) -> bool:
        """Check if a job can start given concurrency limits."""
        if not job.pipeline:
            return False
        if self.ml_running() and is_ml_job(job):
            return False  # Hard limit: 1 ML job at a time
        if self.running_count() >= self.concurrent_jobs:
            return False
        return True

    @staticmethod
    def _is_ml_tool(tool_name: str) -> bool:
        """Check if a tool requires ML inference."""
        return tool_name in _ML_TOOLS

    def reorder(self, job_id: str, new_index: int) -> None:
        """Move a job to a new position in the queue."""
        with self._lock:
            job = None
            for i, j in enumerate(self.jobs):
                if j.id == job_id:
                    job = j
                    break
            if job is None:
                return
            self.jobs.remove(job)
            new_index = max(0, min(new_index, len(self.jobs)))
            self.jobs.insert(new_index, job)
