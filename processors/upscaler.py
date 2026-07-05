"""Upscaler processor — Real-ESRGAN frame-by-frame upscaling."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.job import Job
from core.models_registry import ensure_model
from processors.frame_processor import FrameProcessor

logger = logging.getLogger(__name__)


class UpscalerProcessor(FrameProcessor):
    """Real-ESRGAN video upscaler.

    Extracts frames, runs Real-ESRGAN inference, re-encodes to video.
    Model selection (registry key, RRDBNet blocks, native scale):
      - 2x            → realesrgan-x2plus (23 blocks, scale 2)
      - 4x general    → realesrgan-x4plus (23 blocks, scale 4)
      - 4x anime      → realesrgan-x4plus-anime (6 blocks, scale 4)
    """

    def __init__(self) -> None:
        super().__init__()
        self._upsampler = None
        self._cv2 = None
        self._scale = 4

    @staticmethod
    def select_model(params: dict) -> tuple[str, int, int]:
        """Return (registry_key, num_blocks, native_scale) for the job params."""
        scale = UpscalerProcessor.get_scale_factor(params)
        model = params.get("model", "RealESRGAN_x4plus")
        if scale == 2:
            # No 2x anime weights upstream — x2plus covers both
            return "realesrgan-x2plus", 23, 2
        if "anime" in str(model).lower():
            return "realesrgan-x4plus-anime", 6, 4
        return "realesrgan-x4plus", 23, 4

    def setup_model(self, job: Job) -> None:
        """Load Real-ESRGAN once for the whole job.

        Missing optional ML deps → fall back to copying frames (with a
        warning). A missing/undownloadable model file fails the job.
        """
        from core.vram_manager import vram_manager

        self._scale = self.get_scale_factor(job.params)
        model_key, num_blocks, native_scale = self.select_model(job.params)

        try:
            import cv2
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
        except ImportError as e:
            logger.warning(
                "Real-ESRGAN dependencies not installed (%s) — frames will be copied unchanged", e
            )
            self._upsampler = None
            return

        model_path = ensure_model(model_key)  # FileNotFoundError → job fails

        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=num_blocks, num_grow_ch=32, scale=native_scale,
        )
        self._cv2 = cv2
        self._upsampler = RealESRGANer(
            scale=native_scale,
            model_path=str(model_path),
            model=model,
            tile=vram_manager.recommended_tile,
            tile_pad=10,
            pre_pad=0,
            half=vram_manager.device != "cpu",
        )
        logger.info("Loaded %s (scale %dx)", model_key, self._scale)

    def teardown_model(self) -> None:
        self._upsampler = None
        self._cv2 = None

    def process_frame(self, frame_path: Path, output_path: Path, job: Job) -> None:
        """Upscale a single frame with the preloaded model."""
        if job.cancelled:
            return

        if self._upsampler is None:
            # Dependencies missing — pass frames through unchanged
            shutil.copy2(frame_path, output_path)
            return

        img = self._cv2.imread(str(frame_path), self._cv2.IMREAD_UNCHANGED)
        output, _ = self._upsampler.enhance(img, outscale=self._scale)
        self._cv2.imwrite(str(output_path), output)

    @staticmethod
    def get_scale_factor(params: dict) -> int:
        """Get scale factor from params (2 or 4; accepts int or "2x"/"4x")."""
        scale = params.get("scale", 4)
        if isinstance(scale, str):
            return 2 if "2" in scale else 4
        try:
            return 2 if int(scale) == 2 else 4
        except (TypeError, ValueError):
            return 4
