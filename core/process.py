"""Cancellable subprocess helper for long-running FFmpeg/Demucs steps.

subprocess.run() blocks until the child exits, so a job cancelled (or an
app closed) during frame extraction, re-encoding or stem separation could
not stop until the step finished. run_cancellable() polls a cancel flag and
terminates the child instead.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

_POLL_SECONDS = 0.2


class Cancelled(Exception):
    """Raised when a subprocess was stopped because the job was cancelled."""


def run_cancellable(
    cmd: Sequence[str],
    is_cancelled: Callable[[], bool],
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run cmd capturing text output; stop it early if is_cancelled() turns true.

    Raises Cancelled after terminating the child on cancellation, and
    subprocess.TimeoutExpired (child killed) when timeout elapses.
    """
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
        # Own process group so cancelling also stops grandchildren (a child
        # that outlives its parent keeps the output pipes open and would
        # make communicate() wait for it).
        start_new_session=(sys.platform != "win32"),
    )
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while True:
            try:
                stdout, stderr = proc.communicate(timeout=_POLL_SECONDS)
                return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                pass
            if is_cancelled():
                _stop(proc)
                raise Cancelled()
            if deadline is not None and time.monotonic() > deadline:
                _stop(proc)
                raise subprocess.TimeoutExpired(cmd, timeout)
    except BaseException:
        if proc.poll() is None:
            _stop(proc)
        raise


def _signal(proc: subprocess.Popen, sig: int, fallback) -> None:
    """Signal the child's whole process group (POSIX), else just the child."""
    if sys.platform != "win32":
        try:
            os.killpg(proc.pid, sig)
            return
        except (ProcessLookupError, PermissionError):
            pass
    fallback()


def _stop(proc: subprocess.Popen) -> None:
    _signal(proc, signal.SIGTERM, proc.terminate)
    try:
        proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        _signal(proc, getattr(signal, "SIGKILL", signal.SIGTERM), proc.kill)
        proc.communicate()
