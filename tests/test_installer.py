"""Tests for `videocraft setup` planning (no packages are installed)."""

from unittest.mock import patch

from videocraft import installer


def test_nvidia_uses_default_pypi_torch_for_new_drivers():
    with patch.object(installer, "detect_cuda_version", return_value=(13, 0)):
        label, cmds = installer.plan("nvidia", None)
    assert "CUDA" in label
    assert "--index-url" not in cmds[0]
    assert any(a.startswith("torch") for a in cmds[0])


def test_cpu_uses_cpu_index():
    _, cmds = installer.plan("cpu", None)
    assert cmds[0][cmds[0].index("--index-url") + 1] == installer._CPU_INDEX


def test_custom_index_overrides_gpu_choice():
    _, cmds = installer.plan("nvidia", "https://example.org/rocm")
    assert cmds[0][cmds[0].index("--index-url") + 1] == "https://example.org/rocm"


def test_auto_follows_detection():
    with patch.object(installer, "detect_nvidia", return_value=True):
        assert "CUDA" in installer.plan("auto", None)[0]
    with patch.object(installer, "detect_nvidia", return_value=False):
        assert "CPU" in installer.plan("auto", None)[0]


def test_ml_requirements_exclude_torch():
    reqs = installer.ml_requirements()
    assert reqs and not any(r.startswith(("torch", "torchvision")) for r in reqs)
    assert any(r.startswith("realesrgan") for r in reqs)


def test_detect_nvidia_false_without_smi():
    with patch("shutil.which", return_value=None):
        assert installer.detect_nvidia() is False


def test_cuda_index_follows_driver_version():
    base = installer._INDEX_BASE
    assert installer.cuda_index_url((13, 0)) is None            # default PyPI = newest CUDA
    assert installer.cuda_index_url((12, 9)) == f"{base}/cu128"
    assert installer.cuda_index_url((12, 6)) == f"{base}/cu126"
    assert installer.cuda_index_url((12, 2)) == f"{base}/cu121"
    assert installer.cuda_index_url((11, 8)) == f"{base}/cu118"
    assert installer.cuda_index_url(None) == f"{base}/cu126"    # unreadable → conservative


def test_nvidia_plan_uses_matching_cuda_index():
    with patch.object(installer, "detect_cuda_version", return_value=(12, 4)):
        _, cmds = installer.plan("nvidia", None)
    assert cmds[0][cmds[0].index("--index-url") + 1].endswith("/cu124")


def test_detect_cuda_version_parses_nvidia_smi():
    fake = type("R", (), {"stdout": "| NVIDIA-SMI 550.54  Driver Version: 550.54  CUDA Version: 12.4 |"})()
    with patch("subprocess.run", return_value=fake):
        assert installer.detect_cuda_version() == (12, 4)


def test_patch_basicsr_fixes_removed_torchvision_import(tmp_path, monkeypatch):
    pkg = tmp_path / "basicsr"
    (pkg / "data").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    f = pkg / "data" / "degradations.py"
    f.write_text("from torchvision.transforms.functional_tensor import rgb_to_grayscale\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    assert installer.patch_basicsr() == str(f)
    assert "functional import rgb_to_grayscale" in f.read_text()
    assert installer.patch_basicsr() is None  # idempotent
