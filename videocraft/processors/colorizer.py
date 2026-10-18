"""Colorizer processor — DDColor and Deoldify backends."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from videocraft.core.job import Job
from videocraft.core.models_registry import ensure_model
from videocraft.processors.frame_processor import FrameProcessor

logger = logging.getLogger(__name__)

# (backend, style) → registry key
_MODEL_KEYS = {
    ("ddcolor", "artistic"): "ddcolor-artistic",
    ("ddcolor", "stable"): "ddcolor-modelscope",
    ("ddcolor", "video"): "ddcolor-artistic",  # ddcolor has no video model
    ("deoldify", "artistic"): "deoldify-artistic",
    ("deoldify", "stable"): "deoldify-stable",
    ("deoldify", "video"): "deoldify-video",
}


class ColorizerProcessor(FrameProcessor):
    """Video colorization processor.

    Supports two backends:
    - DDColor: ddcolor-artistic, ddcolor-modelscope
    - Deoldify: Artistic, Stable, Video modes

    Preserves luminance (Y channel) from the original grayscale frame;
    only takes chroma from the model output.

    NOTE: neither backend's inference package is installable from PyPI yet;
    until they are vendored (tracked for a later phase), frames pass
    through unchanged with a warning. Model weights resolve through the
    registry so downloads and pre-flight checks already work.
    """

    def __init__(self) -> None:
        super().__init__()
        self._pipeline = None
        self._backend = "ddcolor"
        self._style = "artistic"
        self._saturation = 1.0
        self._cv2 = None
        self._np = None

    def setup_model(self, job: Job) -> None:
        """Load the colorization model once for the whole job."""
        self._backend = self.get_backend(job)
        self._style = self.get_style(job.params)
        self._saturation = self.get_saturation(job.params)
        self._pipeline = None

        try:
            import cv2
            import numpy as np
        except ImportError as e:
            logger.warning(
                "Colorizer dependencies not installed (%s) — frames will be copied unchanged", e
            )
            return
        self._cv2, self._np = cv2, np

        model_key = _MODEL_KEYS.get((self._backend, self._style), "ddcolor-artistic")

        if self._backend == "ddcolor":
            try:
                from ddcolor.pipeline import DDColorPipeline
            except ImportError:
                logger.warning(
                    "DDColor package not available — frames will be copied unchanged"
                )
                return
            import torch
            from videocraft.core.vram_manager import vram_manager
            model_path = ensure_model(model_key)  # may raise → job fails
            self._pipeline = DDColorPipeline(
                str(model_path), device=torch.device(vram_manager.device)
            )
        elif self._backend == "deoldify":
            try:
                from deoldify.visualize import get_image_colorizer  # noqa: F401
            except ImportError:
                logger.warning(
                    "Deoldify package not available — frames will be copied unchanged"
                )
                return
            model_path = ensure_model(model_key)  # may raise → job fails
            render_factor = 25 if self._style == "artistic" else 35
            self._pipeline = get_image_colorizer(
                root_folder=model_path.parent.parent,
                artistic=self._style == "artistic",
                render_factor=render_factor,
            )
        else:
            logger.error("Unknown colorizer backend: %s", self._backend)

    def teardown_model(self) -> None:
        self._pipeline = None
        self._cv2 = self._np = None

    def process_frame(self, frame_path: Path, output_path: Path, job: Job) -> None:
        """Colorize a single frame with the preloaded model."""
        if job.cancelled:
            return

        if self._pipeline is None:
            shutil.copy2(frame_path, output_path)
            return

        cv2 = self._cv2
        img = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        y_channel = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)[:, :, 0]

        if self._backend == "ddcolor":
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            colored = self._pipeline(gray)
        else:
            colored = self._pipeline.get_transformed_image(str(frame_path))

        if self._saturation != 1.0:
            colored = self._apply_saturation(colored, self._saturation)

        # Preserve original luminance, take chroma from the model
        result_ycbcr = cv2.cvtColor(colored, cv2.COLOR_BGR2YCrCb)
        result_ycbcr[:, :, 0] = y_channel
        result_bgr = cv2.cvtColor(result_ycbcr, cv2.COLOR_YCrCb2BGR)
        cv2.imwrite(str(output_path), result_bgr)

    @staticmethod
    def _apply_saturation(img, saturation: float):
        """Apply saturation adjustment to an image."""
        import cv2
        import numpy as np
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        s = np.clip(s.astype(np.float32) * saturation, 0, 255).astype(np.uint8)
        hsv = cv2.merge([h, s, v])
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    @staticmethod
    def get_backend(job: Job) -> str:
        """Get backend from job params."""
        return job.params.get("backend", "ddcolor")

    @staticmethod
    def get_style(params: dict) -> str:
        """Get style from params."""
        valid = {"artistic", "stable", "video"}
        style = params.get("style", "artistic").lower()
        return style if style in valid else "artistic"

    @staticmethod
    def get_saturation(params: dict) -> float:
        """Get saturation from params (0.0-3.0, matching the UI range)."""
        return max(0.0, min(3.0, params.get("saturation", 1.0)))
