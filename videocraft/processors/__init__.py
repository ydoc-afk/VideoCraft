"""Processors — FFmpeg converter, upscaler, denoiser, colorizer, HDR, audio."""

from videocraft.processors.converter import ConverterProcessor
from videocraft.processors.upscaler import UpscalerProcessor
from videocraft.processors.denoiser import DenoiserProcessor
from videocraft.processors.colorizer import ColorizerProcessor
from videocraft.processors.hdr_converter import HDRConverterProcessor
from videocraft.processors.audio.vocal_remover import VocalRemoverProcessor
from videocraft.processors.audio.upmixer import AudioUpmixerProcessor

__all__ = [
    "ConverterProcessor",
    "UpscalerProcessor",
    "DenoiserProcessor",
    "ColorizerProcessor",
    "HDRConverterProcessor",
    "VocalRemoverProcessor",
    "AudioUpmixerProcessor",
]
