"""Tests for core.vram_manager — CUDA detection and VRAM recommendations."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock
from pathlib import Path


def _mock_torch(has_cuda: bool, vram_gb: float = 0.0):
    """Inject a mock torch module into sys.modules."""
    torch = MagicMock()
    torch.cuda.is_available.return_value = has_cuda
    if has_cuda and vram_gb > 0:
        props = MagicMock()
        props.total_memory = int(vram_gb * 1024**3)
        torch.cuda.get_device_properties.return_value = props
    sys.modules["torch"] = torch
    return torch


def _cleanup_torch():
    """Remove mock torch from sys.modules."""
    sys.modules.pop("torch", None)


def test_cpu_only_defaults():
    """When CUDA is unavailable, manager falls back to CPU."""
    _mock_torch(has_cuda=False)
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.has_cuda is False
        assert mgr.device == "cpu"
        assert mgr.total_vram_gb == 0.0
        assert mgr.recommended_batch == 1
        assert mgr.recommended_tile == 96
    finally:
        _cleanup_torch()
        # Force reimport
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]


def test_high_vram_recommendations():
    """>= 24 GB VRAM gets aggressive batch/tile settings."""
    _mock_torch(has_cuda=True, vram_gb=24)
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.has_cuda is True
        assert mgr.device == "cuda"
        assert mgr.recommended_batch == 4
        assert mgr.recommended_tile == 512
    finally:
        _cleanup_torch()
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]


def test_mid_vram_recommendations():
    """12-24 GB VRAM gets moderate settings."""
    _mock_torch(has_cuda=True, vram_gb=16)
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.recommended_batch == 2
        assert mgr.recommended_tile == 256
    finally:
        _cleanup_torch()
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]


def test_low_vram_recommendations():
    """6-12 GB VRAM gets conservative settings."""
    _mock_torch(has_cuda=True, vram_gb=8)
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.recommended_batch == 1
        assert mgr.recommended_tile == 128
    finally:
        _cleanup_torch()
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]


def test_very_low_vram_recommendations():
    """< 6 GB VRAM gets minimal settings."""
    _mock_torch(has_cuda=True, vram_gb=4)
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.recommended_batch == 1
        assert mgr.recommended_tile == 96
    finally:
        _cleanup_torch()
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]


def test_clamp_tile():
    """User tile size is clamped to safe maximum."""
    _mock_torch(has_cuda=True, vram_gb=8)  # tile=128
    try:
        from core.vram_manager import VRAMManager
        mgr = VRAMManager()
        mgr.probe()

        assert mgr.clamp_tile(256) == 128  # user wants 256, clamped to 128
        assert mgr.clamp_tile(64) == 64     # user wants 64, kept as-is
    finally:
        _cleanup_torch()
        if "core.vram_manager" in sys.modules:
            del sys.modules["core.vram_manager"]
