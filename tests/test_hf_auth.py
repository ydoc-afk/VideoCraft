"""Hugging Face token storage, header safety, and auth-aware downloads."""

import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from videocraft.core import hf_auth, models_registry


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("VIDEOCRAFT_MODELS_DIR", str(tmp_path / "models"))
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def test_save_get_remove_token():
    assert hf_auth.get_token() is None
    hf_auth.save_token("  hf_abc123  ")
    assert hf_auth.get_token() == "hf_abc123"
    hf_auth.save_token("")
    assert hf_auth.get_token() is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_token_file_is_owner_only():
    hf_auth.save_token("hf_secret")
    assert stat.S_IMODE(hf_auth.token_path().stat().st_mode) == 0o600


def test_env_var_wins_over_saved_file(monkeypatch):
    hf_auth.save_token("hf_file")
    monkeypatch.setenv("HF_TOKEN", "hf_env")
    assert hf_auth.get_token() == "hf_env"
    assert hf_auth.saved_token() == "hf_file"


def test_header_only_for_huggingface_https_hosts():
    hf_auth.save_token("hf_tok")
    assert hf_auth.auth_headers("https://huggingface.co/a/b/resolve/main/x.pth") == {
        "Authorization": "Bearer hf_tok"
    }
    assert hf_auth.auth_headers("https://cdn-lfs.huggingface.co/x") != {}
    for other in (
        "https://github.com/xinntao/x.pth",
        "http://huggingface.co/x",                 # not https
        "https://huggingface.co.evil.example/x",   # lookalike host
        "https://evilhuggingface.co/x",
    ):
        assert hf_auth.auth_headers(other) == {}, other


def test_no_header_without_token():
    assert hf_auth.auth_headers("https://huggingface.co/x") == {}


def test_validate_token_messages():
    def resp(code, body=None):
        r = MagicMock(status_code=code)
        r.json.return_value = body or {}
        return r

    with patch("requests.get", return_value=resp(200, {"name": "cody"})):
        ok, msg = hf_auth.validate_token("hf_x")
    assert ok and "cody" in msg
    with patch("requests.get", return_value=resp(401)):
        assert hf_auth.validate_token("hf_x")[0] is False
    assert hf_auth.validate_token("   ") == (False, "Paste a token first.")


def _fake_get(status):
    resp = MagicMock(status_code=status)
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    resp.iter_content.return_value = [b"weights"]
    if status >= 400:
        import requests
        resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return resp


def test_ensure_model_raises_auth_error_on_429_and_sends_token():
    hf_auth.save_token("hf_tok")
    with patch("requests.get", return_value=_fake_get(429)) as get:
        with pytest.raises(hf_auth.DownloadAuthError) as exc:
            models_registry.ensure_model("ddcolor-artistic")
    assert exc.value.status == 429
    assert isinstance(exc.value, FileNotFoundError)     # processors' existing contract
    assert "Settings" in str(exc.value)
    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer hf_tok"}


def test_ensure_model_does_not_send_token_to_github(monkeypatch):
    import hashlib
    hf_auth.save_token("hf_tok")
    # The fake download is b"weights"; pin its digest so the checksum passes
    monkeypatch.setitem(
        models_registry.MODELS["realesrgan-x4plus"], "sha256", hashlib.sha256(b"weights").hexdigest()
    )
    with patch("requests.get", return_value=_fake_get(200)) as get:
        path = models_registry.ensure_model("realesrgan-x4plus")
    assert path.read_bytes() == b"weights"
    assert get.call_args.kwargs["headers"] == {}


def test_github_403_is_not_reported_as_a_token_problem():
    with patch("requests.get", return_value=_fake_get(403)):
        with pytest.raises(FileNotFoundError) as exc:
            models_registry.ensure_model("realesrgan-x4plus")
    assert not isinstance(exc.value, hf_auth.DownloadAuthError)


def test_download_worker_flags_auth_failures(tmp_path):
    from videocraft.ui.dialogs.model_manager_dialog import _DownloadWorker

    worker = _DownloadWorker("https://huggingface.co/x/y/resolve/main/m.pth", tmp_path / "m.pth")
    errors = []
    worker.download_error.connect(errors.append)
    with patch("requests.get", return_value=MagicMock(status_code=401)):
        worker.run()
    assert worker.auth_status == 401 and errors


def test_token_dialog_saves_and_settings_status(tmp_path):
    from videocraft.ui.dialogs.hf_token_dialog import HFTokenDialog
    from videocraft.core.config import AppConfig
    from videocraft.ui.dialogs.settings_dialog import SettingsDialog

    dlg = HFTokenDialog(status=429)
    assert "limiting" in dlg.findChildren(type(dlg.lbl_status))[0].text().lower()
    dlg.le_token.setText("hf_new")
    dlg._on_save()
    assert hf_auth.saved_token() == "hf_new"

    settings = SettingsDialog(AppConfig.defaults())
    assert "saved" in settings.lbl_hf_status.text().lower()
    settings._on_hf_remove()
    assert hf_auth.saved_token() is None
    assert not settings.btn_hf_remove.isEnabled()
