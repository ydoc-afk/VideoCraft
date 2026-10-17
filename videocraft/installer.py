"""`videocraft setup` — install the optional AI packages for this machine.

PyTorch has to match the user's GPU, so it is installed first from the right
package index; everything else the AI tools need comes from the `ml` extra in
pyproject.toml (read from the installed package metadata so there is a single
list). A final check imports each tool's dependencies and reports what works.
"""

from __future__ import annotations

import importlib.metadata
import re
import shlex
import shutil
import subprocess
import sys

# Used only when the package metadata is unavailable (e.g. running from a
# source checkout that was never installed).
_FALLBACK_ML = [
    "basicsr>=1.4.2", "realesrgan>=0.3.0", "opencv-python>=4.8.0",
    "einops", "timm", "demucs>=4.0.0",
]
_TORCH = ["torch>=2.1.0", "torchvision>=0.16.0"]
_INDEX_BASE = "https://download.pytorch.org/whl"
_CPU_INDEX = f"{_INDEX_BASE}/cpu"

# Newest CUDA build of PyTorch each driver generation can run, newest first:
# (minimum driver CUDA version, PyTorch index name). The default PyPI wheel
# targets the newest CUDA (13.x), which older drivers cannot use, so anything
# below 13 must pick an older index explicitly. None = plain PyPI.
_CUDA_INDEXES: list[tuple[tuple[int, int], str | None]] = [
    ((13, 0), None),
    ((12, 8), "cu128"),
    ((12, 6), "cu126"),
    ((12, 4), "cu124"),
    ((12, 1), "cu121"),
    ((11, 8), "cu118"),
]
_UNKNOWN_CUDA_INDEX = "cu126"


def detect_nvidia() -> bool:
    """True if an NVIDIA GPU is visible to the driver."""
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=15
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and "GPU" in result.stdout


def detect_cuda_version() -> tuple[int, int] | None:
    """Highest CUDA version the installed NVIDIA driver supports, if readable."""
    try:
        out = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=15
        ).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None
    m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


def cuda_index_url(version: tuple[int, int] | None) -> str | None:
    """PyTorch package index for a driver's CUDA version (None = default PyPI)."""
    if version is None:
        return f"{_INDEX_BASE}/{_UNKNOWN_CUDA_INDEX}"
    for minimum, name in _CUDA_INDEXES:
        if version >= minimum:
            return None if name is None else f"{_INDEX_BASE}/{name}"
    return None  # driver older than any supported build — let pip try PyPI


def ml_requirements() -> list[str]:
    """Requirements of the `ml` extra, minus PyTorch (installed separately)."""
    try:
        requires = importlib.metadata.requires("videocraft") or []
    except importlib.metadata.PackageNotFoundError:
        return list(_FALLBACK_ML)
    out = []
    for req in requires:
        if 'extra == "ml"' not in req and "extra == 'ml'" not in req:
            continue
        spec = req.split(";")[0].strip()
        if re.match(r"(torch|torchvision)\b", spec):
            continue
        out.append(spec)
    return out or list(_FALLBACK_ML)


def plan(gpu: str, torch_index_url: str | None) -> tuple[str, list[list[str]]]:
    """Return (description, pip argument lists) for the chosen configuration."""
    pip = [sys.executable, "-m", "pip", "install"]
    if torch_index_url:
        label = f"PyTorch from {torch_index_url}"
        torch_cmd = [*pip, *_TORCH, "--index-url", torch_index_url]
    else:
        if gpu == "auto":
            gpu = "nvidia" if detect_nvidia() else "cpu"
        if gpu == "nvidia":
            index = cuda_index_url(detect_cuda_version())
            label = "PyTorch with CUDA (NVIDIA GPU)"
            torch_cmd = [*pip, *_TORCH]
            if index:
                torch_cmd += ["--index-url", index]
        else:
            label = "PyTorch for CPU (no NVIDIA GPU detected or requested)"
            torch_cmd = [*pip, *_TORCH, "--index-url", _CPU_INDEX]
    return label, [torch_cmd, [*pip, *ml_requirements()]]


def patch_basicsr() -> str | None:
    """Fix basicsr's import of a torchvision module that newer releases removed.

    basicsr 1.4.2 does `from torchvision.transforms.functional_tensor import
    rgb_to_grayscale`; that module is gone in torchvision >= 0.17 and the
    function lives in `torchvision.transforms.functional`. Returns the patched
    file path, or None if nothing needed changing.
    """
    import importlib.util

    spec = importlib.util.find_spec("basicsr")
    if spec is None or not spec.submodule_search_locations:
        return None
    target = next(
        (p for loc in spec.submodule_search_locations
         if (p := __import__("pathlib").Path(loc) / "data" / "degradations.py").exists()),
        None,
    )
    if target is None:
        return None
    text = target.read_text()
    old = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
    if old not in text:
        return None
    target.write_text(text.replace(old, "from torchvision.transforms.functional import rgb_to_grayscale"))
    return str(target)


# What each check runs, in a fresh interpreter so one failure can't hide another.
_CHECKS = {
    "PyTorch": (
        "import torch; "
        "print('CUDA GPU: ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() "
        "else 'CPU only (no CUDA device)')"
    ),
    "Upscaler (Real-ESRGAN)": "from realesrgan import RealESRGANer; print('ok')",
    "Denoiser (SCUNet)": "import einops, timm, cv2; print('ok')",
    "Vocal remover (Demucs)": "import demucs; print('ok')",
}


def verify() -> dict[str, tuple[bool, str]]:
    results = {}
    for name, code in _CHECKS.items():
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
        )
        ok = proc.returncode == 0
        detail = proc.stdout.strip() if ok else (proc.stderr.strip().splitlines() or ["failed"])[-1]
        results[name] = (ok, detail)
    return results


def run_setup(gpu: str = "auto", torch_index_url: str | None = None, dry_run: bool = False) -> int:
    label, commands = plan(gpu, torch_index_url)
    print(f"VideoCraft setup — installing {label}\n")

    if shutil.which("ffmpeg") is None:
        print("! FFmpeg was not found on your PATH. Install it first, for example:")
        print("    Debian/Ubuntu:  sudo apt install ffmpeg")
        print("    Fedora:         sudo dnf install ffmpeg\n")

    if sys.version_info >= (3, 13):
        print("! Python 3.13 detected: the Real-ESRGAN dependency 'basicsr' does not build on it yet.")
        print("  If the install below fails on basicsr, use Python 3.12 or 3.11 (install.sh prefers them).\n")

    for cmd in commands:
        print("$ " + shlex.join(cmd))
        if dry_run:
            continue
        if subprocess.run(cmd).returncode != 0:
            print("\nInstallation failed — see the pip output above.")
            return 1

    if dry_run:
        return 0

    patched = patch_basicsr()
    if patched:
        print(f"\nApplied the torchvision compatibility fix to {patched}")

    print("\nChecking the installation…")
    failed = False
    for name, (ok, detail) in verify().items():
        print(f"  [{'ok' if ok else 'FAIL'}] {name}: {detail}")
        failed = failed or not ok
    if failed:
        print("\nSome AI tools are not usable yet. Fix the failures above and run "
              "`videocraft setup` again.")
        return 1
    print("\nAll set. Start VideoCraft with:  videocraft")
    return 0
