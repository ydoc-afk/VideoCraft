"""CUDA VRAM detection and adaptive batch/tile sizing."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class VRAMManager:
    """Detect available GPU memory and recommend safe batch/tile sizes."""

    def __init__(self) -> None:
        self.has_cuda: bool = False
        self.device: str = "cpu"
        self.total_vram_gb: float = 0.0
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
                self.total_vram_gb = props.total_memory / (1024**3)
                self._set_recommendations()
                logger.info(
                    "CUDA detected: %.1f GB VRAM — batch=%d, tile=%d",
                    self.total_vram_gb,
                    self.recommended_batch,
                    self.recommended_tile,
                )
            except Exception as e:
                logger.warning("CUDA query failed (%s) — falling back to CPU", e)
                self.has_cuda = False
                self.device = "cpu"
        else:
            logger.warning("No CUDA GPU detected — running on CPU (slow for ML tools)")

    def _set_recommendations(self) -> None:
        """Set batch/tile recommendations based on available VRAM."""
        if self.total_vram_gb >= 24:
            self.recommended_batch, self.recommended_tile = 4, 512
        elif self.total_vram_gb >= 12:
            self.recommended_batch, self.recommended_tile = 2, 256
        elif self.total_vram_gb >= 6:
            self.recommended_batch, self.recommended_tile = 1, 128
        else:
            self.recommended_batch, self.recommended_tile = 1, 96

    def clamp_tile(self, user_tile: int) -> int:
        """Clamp a user-specified tile size to the safe maximum."""
        return min(user_tile, self.recommended_tile)

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
