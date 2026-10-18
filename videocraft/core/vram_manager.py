"""CUDA VRAM detection and adaptive batch/tile sizing.

Tile size is the edge (in pixels) of the sub-tiles Real-ESRGAN processes one
at a time. Bigger tiles mean fewer seams and less per-tile overhead (faster)
but cost more VRAM; tiling is what keeps a 4x upscale from OOM-ing. Rather
than make the user guess, we detect the card and pick a tile that fits its
memory class — small for a 4 GB laptop GPU, large for a 24 GB 4090 or a
32 GB 5090 — while still letting them override it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# VRAM ladder: (min_total_gb, tile, batch, tier). First row whose threshold
# the card meets wins, so keep it in descending order. Tile sizes are chosen
# to leave headroom for the OS/other apps on a typical card of that class.
_VRAM_LADDER: list[tuple[float, int, int, str]] = [
    (32, 1024, 6, "ultra"),    # RTX 5090, A6000, and larger
    (24, 768, 4, "high"),      # RTX 4090 / 3090 (Ti)
    (16, 512, 3, "high"),      # RTX 4080 / 5080 / 4060 Ti 16G
    (12, 384, 2, "medium"),    # RTX 4070 / 3060 12G
    (8, 256, 1, "medium"),     # RTX 3070 / 4060 Ti 8G
    (6, 192, 1, "low"),        # RTX 2060 / 3050
    (4, 128, 1, "low"),        # GTX 1650 and small 4 GB cards
    (0, 96, 1, "minimal"),     # anything smaller / very old
]


class VRAMManager:
    """Detect available GPU memory and recommend safe batch/tile sizes."""

    def __init__(self) -> None:
        self.has_cuda: bool = False
        self.device: str = "cpu"
        self.gpu_name: str = ""
        self.total_vram_gb: float = 0.0
        self.free_vram_gb: float = 0.0
        self.tier: str = "cpu"
        self.recommended_batch: int = 1
        self.recommended_tile: int = 96

    def probe(self) -> None:
        """Query GPU VRAM and set safe defaults."""
        try:
            import torch
            self.has_cuda = torch.cuda.is_available()
        except ImportError:
            self.has_cuda = False
            logger.warning("PyTorch not installed — running on CPU")

        if self.has_cuda:
            self.device = "cuda"
            try:
                import torch
                props = torch.cuda.get_device_properties(0)
                self.gpu_name = str(getattr(props, "name", "") or "")
                self.total_vram_gb = props.total_memory / (1024**3)
                self.free_vram_gb = self._query_free_vram()
                self._set_recommendations()
                logger.info(
                    "CUDA detected: %s — %.1f GB VRAM (%s tier) → tile=%d, batch=%d",
                    self.gpu_name or "unknown GPU",
                    self.total_vram_gb,
                    self.tier,
                    self.recommended_tile,
                    self.recommended_batch,
                )
            except Exception as e:
                logger.warning("CUDA query failed (%s) — falling back to CPU", e)
                self.has_cuda = False
                self.device = "cpu"
                self.tier = "cpu"
        else:
            logger.warning("No CUDA GPU detected — running on CPU (slow for ML tools)")

    def apply_device_preference(self, preference: str) -> None:
        """Apply the user's device setting ("auto" | "cuda:N" | "cpu").

        "cpu" forces CPU even when CUDA is present; a "cuda:N" choice or
        "auto" falls back to CPU when no CUDA device was detected.
        """
        if preference == "cpu" or not self.has_cuda:
            self.device = "cpu"
        elif preference.startswith("cuda"):
            self.device = preference
        else:
            self.device = "cuda"
        logger.info("Compute device: %s (setting: %s)", self.device, preference)

    @staticmethod
    def _query_free_vram() -> float:
        """Return currently-free VRAM in GB, or 0.0 if it can't be determined."""
        try:
            import torch
            free_bytes, _total = torch.cuda.mem_get_info()
            # Guard against mocks / odd returns — only trust real ints.
            if isinstance(free_bytes, int):
                return free_bytes / (1024**3)
        except (ImportError, RuntimeError, TypeError, ValueError, OSError):
            pass
        return 0.0

    def _set_recommendations(self) -> None:
        """Pick tile/batch/tier from the VRAM ladder.

        Classification uses total VRAM (the card's class). If far less memory
        is actually free right now — e.g. another app is using the GPU — step
        down one rung so we don't OOM on a busy card.
        """
        gb = self.total_vram_gb
        for i, (threshold, tile, batch, tier) in enumerate(_VRAM_LADDER):
            if gb >= threshold:
                # If free memory is known and tight, drop a rung for safety.
                if (
                    self.free_vram_gb
                    and i + 1 < len(_VRAM_LADDER)
                    and self.free_vram_gb < _VRAM_LADDER[i][0]
                ):
                    _th, tile, batch, tier = _VRAM_LADDER[i + 1]
                    logger.info(
                        "Only %.1f GB VRAM free — stepping down to %s tier (tile=%d)",
                        self.free_vram_gb, tier, tile,
                    )
                self.recommended_batch = batch
                self.recommended_tile = tile
                self.tier = tier
                return
        # _VRAM_LADDER ends with a 0-threshold row, so this is unreachable.
        self.recommended_batch, self.recommended_tile, self.tier = 1, 96, "minimal"

    def resolve_tile(self, user_tile: int | None) -> int:
        """Resolve a UI tile value to the effective tile size.

        0 or None means "Auto" → the VRAM-based recommendation. A positive
        value is honored but clamped to the recommended safe maximum so a
        manual setting can't push a small card into OOM.
        """
        if not user_tile:
            return self.recommended_tile
        return min(int(user_tile), self.recommended_tile)

    def clamp_tile(self, user_tile: int) -> int:
        """Clamp a user-specified tile size to the safe maximum."""
        return min(user_tile, self.recommended_tile)

    def summary(self) -> str:
        """Short human-readable description of the detected device."""
        if not self.has_cuda:
            return "CPU (no CUDA GPU)"
        name = self.gpu_name or "GPU"
        return f"{name} — {self.total_vram_gb:.0f} GB ({self.tier} tier)"

    def clear_cache(self) -> None:
        """Clear CUDA cache to free memory between jobs."""
        if self.has_cuda:
            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass


# Module-level singleton — probed on first import
vram_manager = VRAMManager()
vram_manager.probe()
