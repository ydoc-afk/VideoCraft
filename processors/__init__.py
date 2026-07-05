"""Processors — FFmpeg converter, upscaler, denoiser, colorizer, HDR, audio."""

from processors.converter import ConverterProcessor
from processors.upscaler import UpscalerProcessor
from processors.denoiser import DenoiserProcessor
from processors.colorizer import ColorizerProcessor
from processors.hdr_converter import HDRConverterProcessor
from processors.audio.vocal_remover import VocalRemoverProcessor
from processors.audio.upmixer import AudioUpmixerProcessor

__all__ = [
    "ConverterProcessor",
    "UpscalerProcessor",
    "DenoiserProcessor",
    "ColorizerProcessor",
    "HDRConverterProcessor",
    "VocalRemoverProcessor",
    "AudioUpmixerProcessor",
]
