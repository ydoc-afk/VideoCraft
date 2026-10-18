"""Tests for core.vram_manager — CUDA detection and VRAM recommendations."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock
from pathlib import Path


def _mock_torch(has_cuda: bool, vram_gb: float = 0.0, name: str = "Mock GPU",
                free_gb: float | None = None):
    """Inject a mock torch module into sys.modules."""
    torch = MagicMock()
    torch.cuda.is_available.return_value = has_cuda
    if has_cuda and vram_gb > 0:
        props = MagicMock()
        props.total_memory = int(vram_gb * 1024**3)
        props.name = name
        torch.cuda.get_device_properties.return_value = props
        if free_gb is not None:
            torch.cuda.mem_get_info.return_value = (
                int(free_gb * 1024**3), int(vram_gb * 1024**3),
            )
        else:
            # Unknown free memory: return a non-int so the manager ignores it
            torch.cuda.mem_get_info.return_value = (MagicMock(), MagicMock())
    sys.modules["torch"] = torch
    return torch


def _cleanup_torch():
    """Remove mock torch from sys.modules and force a fresh import."""
    sys.modules.pop("torch", None)
    if "videocraft.core.vram_manager" in sys.modules:
        del sys.modules["videocraft.core.vram_manager"]


def _probe(**kwargs):
    """Build a freshly-probed manager with a mocked torch."""
    _mock_torch(**kwargs)
    from videocraft.core.vram_manager import VRAMManager
    mgr = VRAMManager()
    mgr.probe()
    return mgr


def test_cpu_only_defaults():
    """When CUDA is unavailable, manager falls back to CPU."""
    try:
        mgr = _probe(has_cuda=False)
        assert mgr.has_cuda is False
        assert mgr.device == "cpu"
        assert mgr.tier == "cpu"
        assert mgr.total_vram_gb == 0.0
        assert mgr.recommended_tile == 96
    finally:
        _cleanup_torch()


def test_ultra_card_5090():
    """A 32 GB card (5090-class) gets the largest tile / ultra tier."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=32, name="NVIDIA GeForce RTX 5090")
        assert mgr.tier == "ultra"
        assert mgr.recommended_tile == 1024
        assert mgr.recommended_batch == 6
        assert "5090" in mgr.summary()
    finally:
        _cleanup_torch()


def test_high_card_4090():
    """A 24 GB card (4090-class) gets a large tile / high tier."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=24, name="NVIDIA GeForce RTX 4090")
        assert mgr.tier == "high"
        assert mgr.recommended_tile == 768
        assert mgr.recommended_batch == 4
    finally:
        _cleanup_torch()


def test_medium_card_12gb():
    """A 12 GB card gets a moderate tile / medium tier."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=12)
        assert mgr.tier == "medium"
        assert mgr.recommended_tile == 384
    finally:
        _cleanup_torch()


def test_low_card_6gb():
    """A 6 GB card gets a small tile / low tier."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=6)
        assert mgr.tier == "low"
        assert mgr.recommended_tile == 192
    finally:
        _cleanup_torch()


def test_minimal_card_under_4gb():
    """A tiny card gets the minimal tile."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=2)
        assert mgr.tier == "minimal"
        assert mgr.recommended_tile == 96
    finally:
        _cleanup_torch()


def test_free_memory_steps_down_a_rung():
    """A 24 GB card with little free VRAM is treated as the next rung down."""
    try:
        # 24 GB total but only 10 GB free (< 24 threshold) → step to 16 GB rung
        mgr = _probe(has_cuda=True, vram_gb=24, free_gb=10)
        assert mgr.recommended_tile == 512  # the 16 GB rung's tile
        assert mgr.tier == "high"
    finally:
        _cleanup_torch()


def test_resolve_tile_auto_uses_recommendation():
    """resolve_tile(0/None) returns the VRAM recommendation."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=24)  # recommends 768
        assert mgr.resolve_tile(0) == 768
        assert mgr.resolve_tile(None) == 768
    finally:
        _cleanup_torch()


def test_resolve_tile_manual_is_clamped():
    """A manual tile is honored but clamped to the safe maximum."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=6)  # recommends 192
        assert mgr.resolve_tile(128) == 128   # under the cap → kept
        assert mgr.resolve_tile(512) == 192   # over the cap → clamped
    finally:
        _cleanup_torch()


def test_clamp_tile_backward_compat():
    """clamp_tile still clamps to the safe maximum."""
    try:
        mgr = _probe(has_cuda=True, vram_gb=8)  # recommends 256
        assert mgr.clamp_tile(512) == 256
        assert mgr.clamp_tile(128) == 128
    finally:
        _cleanup_torch()


def test_apply_device_preference():
    """cpu forces CPU on a CUDA box; cuda:N is honored only when CUDA exists."""
    from videocraft.core.vram_manager import VRAMManager

    mgr = VRAMManager()
    mgr.has_cuda = True
    mgr.apply_device_preference("auto")
    assert mgr.device == "cuda"
    mgr.apply_device_preference("cuda:1")
    assert mgr.device == "cuda:1"
    mgr.apply_device_preference("cpu")
    assert mgr.device == "cpu"

    mgr.has_cuda = False
    mgr.apply_device_preference("cuda:0")
    assert mgr.device == "cpu"
