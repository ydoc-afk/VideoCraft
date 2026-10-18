"""Colorizer processor — DDColor (inference code vendored in processors/archs/ddcolor)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from videocraft.core.job import Job
from videocraft.core.models_registry import ensure_model
from videocraft.processors.frame_processor import FrameProcessor

logger = logging.getLogger(__name__)

# style → registry key. DDColor has no dedicated video model, so "video"
# uses the artistic weights.
_MODEL_KEYS = {
    "artistic": "ddcolor-artistic",
    "stable": "ddcolor-modelscope",
    "video": "ddcolor-artistic",
}

# Both released DDColor checkpoints are the "large" (ConvNeXt-L) variant.
_MODEL_SIZE = "large"
_INPUT_SIZE = 512


class ColorizerProcessor(FrameProcessor):
    """Video colorization with DDColor.

    DDColor works per image, so each frame is colorized independently — fast
    motion or scene changes can make colors flicker slightly between frames.
    The original luminance is kept; only chroma comes from the model.

    Needs the optional ML packages (torch, opencv). Without them frames pass
    through unchanged with a warning. A missing or undownloadable model file
    fails the job.
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
        """Load DDColor once for the whole job."""
        self._backend = self.get_backend(job)
        self._style = self.get_style(job.params)
        self._saturation = self.get_saturation(job.params)
        self._pipeline = None

        try:
            import cv2
            import numpy as np
            import torch
        except ImportError as e:
            logger.warning(
                "Colorizer dependencies not installed (%s) — frames will be copied unchanged", e
            )
            return
        self._cv2, self._np = cv2, np

        from videocraft.core.vram_manager import vram_manager
        from videocraft.processors.archs.ddcolor import (
            ColorizationPipeline,
            DDColor,
            build_ddcolor_model,
        )

        model_path = ensure_model(_MODEL_KEYS[self._style])  # may raise → job fails
        device = torch.device(vram_manager.device)
        model = build_ddcolor_model(
            DDColor, model_path=str(model_path), model_size=_MODEL_SIZE,
            input_size=_INPUT_SIZE, device=device,
        )
        self._pipeline = ColorizationPipeline(model, input_size=_INPUT_SIZE, device=device)
        logger.info("Loaded DDColor (%s) on %s", self._style, vram_manager.summary())

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

        # The pipeline converts to Lab and only uses the lightness channel
        colored = self._pipeline.process(img)

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
        """Colorization backend. Only DDColor is supported; anything else
        (e.g. "deoldify" from an older config) falls back to it."""
        backend = job.params.get("backend", "ddcolor")
        if backend != "ddcolor":
            logger.warning("Colorizer backend %r is not supported — using DDColor", backend)
        return "ddcolor"

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
