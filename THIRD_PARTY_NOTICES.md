# Third-party notices

VideoCraft is licensed under the **GNU General Public License v3.0** (see
[LICENSE](LICENSE)). It builds on the projects below, each under its own
license. Licenses are listed as published upstream at the time of writing —
check each project for the authoritative terms.

## Required runtime libraries

| Project | License |
|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GPL v3 (or Riverbank commercial) |
| [qt-material](https://github.com/UN-GCPDS/qt-material) | BSD-2-Clause |
| [qtawesome](https://github.com/spyder-ide/qtawesome) | MIT |
| [NumPy](https://numpy.org/) | BSD-3-Clause |
| [Pillow](https://python-pillow.org/) | HPND |
| [requests](https://github.com/psf/requests) | Apache-2.0 |
| [tqdm](https://github.com/tqdm/tqdm) | MPL-2.0 AND MIT |
| [tomli-w](https://github.com/hukkin/tomli-w) | MIT |

## Optional ML dependencies (installed separately)

| Project | Used for | License |
|---|---|---|
| [PyTorch](https://pytorch.org/) | all ML tools | BSD-3-Clause |
| [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) / [BasicSR](https://github.com/XPixelGroup/BasicSR) | upscaler | BSD-3-Clause / Apache-2.0 |
| [SCUNet](https://github.com/cszn/SCUNet) | denoiser | Apache-2.0 |
| [Demucs](https://github.com/facebookresearch/demucs) | vocal remover | MIT |
| [OpenCV](https://opencv.org/), [einops](https://github.com/arogozhnikov/einops), [timm](https://github.com/huggingface/pytorch-image-models) | image I/O, denoiser | Apache-2.0 / MIT / Apache-2.0 |

`processors/archs/scunet_arch.py` is the SCUNet network definition vendored
from <https://github.com/cszn/SCUNet> (Apache-2.0); local changes are marked
in the file header.

## FFmpeg

VideoCraft runs FFmpeg as an external program; it is not part of this
repository. FFmpeg is licensed under the LGPL v2.1+ or the GPL v2+ depending
on how the binary was built. If you redistribute a build that bundles FFmpeg
(for example an AppImage with a static FFmpeg in `assets/bin/`), you must
also comply with that build's license and provide its corresponding source.

## Model weights

Model weights are **not** distributed with VideoCraft. They are downloaded on
first use from their upstream hosts (GitHub releases of Real-ESRGAN and
KAIR/SCUNet, Hugging Face for DDColor and Deoldify) and remain under the
licenses chosen by their authors. Demucs downloads its own weights.
