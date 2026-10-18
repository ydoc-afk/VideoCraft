"""Abstract base processor — all tools inherit from this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from videocraft.core.job import Job


class BaseProcessor(ABC):
    """Abstract base class for all video/audio processors.

    Subclasses implement process() which yields log line strings.
    The worker thread collects these lines, checks for cancellation,
    and updates the job status.
    """

    @abstractmethod
    def process(self, job: Job):
        """Process a job, yielding log line strings.

        Update job.progress in-place (0.0–1.0).
        Check job.cancelled periodically and stop early if set.
        Clean up temp files in a finally block.

        Yields:
            str: Log line with timestamp and severity.
        """
        ...
