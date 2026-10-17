"""Tests for processors.audio.vocal_remover output handling."""

from pathlib import Path
from unittest.mock import patch

from core.job import Job
from processors.audio.vocal_remover import VocalRemoverProcessor


def _run(tmp_path, out_name, **params):
    job = Job(
        source_path=tmp_path / "in.wav",
        output_path=tmp_path / out_name,
        pipeline=["vocal_remover"],
        params=params,
    )
    proc = VocalRemoverProcessor()
    seen = {}

    def fake_encode(self, src, dst, fmt):
        seen["fmt"] = fmt
        return True

    with patch.object(VocalRemoverProcessor, "_extract_audio", return_value=True), \
         patch.object(VocalRemoverProcessor, "_run_demucs", return_value=True), \
         patch.object(VocalRemoverProcessor, "_mix_stems", return_value=True), \
         patch.object(VocalRemoverProcessor, "_encode_audio", fake_encode), \
         patch("processors.audio.vocal_remover.ffprobe_duration", return_value=1.0):
        list(proc.process(job))
    return job, seen


def test_audio_codec_follows_output_extension(tmp_path):
    """output_format=wav with a .mp3 output must still encode as mp3."""
    job, seen = _run(tmp_path, "out.mp3", output_format="wav")
    assert job.status != "failed"
    assert seen["fmt"]["codec"] == "libmp3lame"


def test_ogg_output_uses_vorbis(tmp_path):
    _, seen = _run(tmp_path, "out.ogg")
    assert seen["fmt"]["codec"] == "libvorbis"


def test_remux_maps_video_optionally():
    """Audio-only sources must not fail on a missing video stream."""
    captured = {}

    def fake_run(cmd, *a, **kw):
        captured["cmd"] = cmd
        class R: returncode = 0; stderr = ""
        return R()

    with patch("processors.audio.vocal_remover.run_cancellable", fake_run):
        VocalRemoverProcessor()._remux_audio(Path("a.mp3"), Path("m.wav"), Path("o.mp4"))
    cmd = captured["cmd"]
    assert cmd[cmd.index("-map") + 1] == "0:v?"
