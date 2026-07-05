"""Denoiser processor — SCUNet frame-by-frame denoising."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.job import Job
from core.models_registry import ensure_model
from processors.frame_processor import FrameProcessor

logger = logging.getLogger(__name__)

# tools-panel model param → registry key
_MODEL_KEYS = {
    "scunet-color-real": "scunet-color-real",
    "scunet-color-gaussian": "scunet-color-gaussian",
    # legacy param values from older configs
    "scunet_color_real_psnr": "scunet-color-real",
    "scunet_gray_gaussian_psnr": "scunet-color-gaussian",
}


class DenoiserProcessor(FrameProcessor):
    """SCUNet video denoiser.

    Extracts frames, runs SCUNet inference (vendored arch in
    processors/archs/scunet_arch.py), re-encodes to video. Requires the
    optional ML deps (torch, einops, timm, opencv); without them frames
    pass through unchanged with a warning.
    """

    def __init__(self) -> None:
        super().__init__()
        self._net = None
        self._cv2 = None
        self._torch = None
        self._np = None

    @staticmethod
    def model_key(params: dict) -> str:
        """Map the job's model param to a registry key."""
        return _MODEL_KEYS.get(params.get("model", ""), "scunet-color-real")

    def setup_model(self, job: Job) -> None:
        """Load SCUNet once for the whole job (or arrange the copy fallback)."""
        try:
            import cv2
            import numpy as np
            import torch
        except ImportError as e:
            logger.warning(
                "SCUNet dependencies not installed (%s) — frames will be copied unchanged", e
            )
            self._net = None
            return

        from core.vram_manager import vram_manager

        try:
            # SCUNet is not part of basicsr — a vendored arch is required.
            from processors.archs.scunet_arch import SCUNet  # noqa: F401
        except ImportError:
            logger.warning(
                "SCUNet architecture not available — frames will be copied unchanged"
            )
            self._net = None
            return

        model_path = ensure_model(self.model_key(job.params))  # may raise → job fails

        device = torch.device(vram_manager.device)
        net = SCUNet(in_nc=3, config=[4, 4, 4, 4, 4, 4, 4], dim=64)
        checkpoint = torch.load(str(model_path), map_location=device, weights_only=True)
        net.load_state_dict(checkpoint)
        net.eval()
        self._net = net.to(device)
        self._cv2, self._torch, self._np = cv2, torch, np
        self._device = device

    def teardown_model(self) -> None:
        self._net = None
        self._cv2 = self._torch = self._np = None

    def process_frame(self, frame_path: Path, output_path: Path, job: Job) -> None:
        """Denoise a single frame with the preloaded model."""
        if job.cancelled:
            return

        if self._net is None:
            shutil.copy2(frame_path, output_path)
            return

        cv2, torch, np = self._cv2, self._torch, self._np
        img = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        img_np = np.transpose(img, (2, 0, 1)).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_np).unsqueeze(0).to(self._device)

        with torch.no_grad():
            result = self._net(img_tensor)

        result = result.squeeze().cpu().numpy()
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
        result = np.transpose(result, (1, 2, 0))
        cv2.imwrite(str(output_path), result)

    @staticmethod
    def get_noise_strength(params: dict) -> int:
        """Get noise strength from params (1-50)."""
        return max(1, min(50, params.get("noise_level", 25)))

    @staticmethod
    def should_remove_artifacts(job: Job) -> bool:
        """Check if artifact removal is enabled."""
        return job.params.get("remove_artifacts", False)
