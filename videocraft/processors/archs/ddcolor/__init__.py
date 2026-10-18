"""DDColor inference code, vendored so the colorizer needs no extra package.

Source: https://github.com/piddnad/DDColor (commit 2adb63f), Apache-2.0 — see
LICENSE in this folder. Only the inference path is included (model, the
ConvNeXt encoder from Meta's ConvNeXt (MIT), decoder utilities, and the
colorization pipeline); training code and the basicsr dependency are not.

Local changes: imports now point at this package; `weights_only=True` when
loading checkpoints; a warning is logged if a checkpoint is missing weights.
"""

from videocraft.processors.archs.ddcolor.model import DDColor
from videocraft.processors.archs.ddcolor.pipeline import (
    ColorizationPipeline,
    build_ddcolor_model,
)

__all__ = ["DDColor", "ColorizationPipeline", "build_ddcolor_model"]
