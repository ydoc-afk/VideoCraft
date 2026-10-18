"""Model checksum verification: download-time checks and the Verify button."""

import hashlib
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from videocraft.core import models_registry as reg

KEY = "realesrgan-x4plus"
CONTENT = b"pretend model weights"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


@pytest.fixture(autouse=True)
def models_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEOCRAFT_MODELS_DIR", str(tmp_path))
    return tmp_path


def _pin(monkeypatch, digest):
    monkeypatch.setitem(reg.MODELS[KEY], "sha256", digest)


def _install(content=CONTENT):
    reg.model_path(KEY).write_bytes(content)


def test_sha256_file_matches_hashlib_and_reports_progress(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"a" * (3 * (1 << 20) + 5))
    seen = []
    assert reg.sha256_file(f, progress=seen.append) == hashlib.sha256(f.read_bytes()).hexdigest()
    assert seen[-1] == f.stat().st_size and len(seen) == 4


def test_sha256_file_can_be_cancelled(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"a" * 10)
    assert reg.sha256_file(f, is_cancelled=lambda: True) == ""


def test_verify_model_statuses(monkeypatch):
    assert reg.verify_model(KEY) == (reg.MISSING, "")

    _install()
    _pin(monkeypatch, DIGEST)
    assert reg.verify_model(KEY) == (reg.VERIFIED, DIGEST)

    _pin(monkeypatch, "0" * 64)
    assert reg.verify_model(KEY) == (reg.MISMATCH, DIGEST)

    _pin(monkeypatch, None)
    assert reg.verify_model(KEY) == (reg.UNVERIFIED, DIGEST)


def _fake_get(content):
    resp = MagicMock(status_code=200)
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    resp.iter_content.return_value = [content]
    return resp


def test_download_with_matching_checksum_is_kept(monkeypatch):
    _pin(monkeypatch, DIGEST)
    with patch("requests.get", return_value=_fake_get(CONTENT)):
        path = reg.ensure_model(KEY)
    assert path.read_bytes() == CONTENT


def test_download_with_wrong_checksum_is_discarded_with_clear_error(monkeypatch):
    _pin(monkeypatch, "0" * 64)
    with patch("requests.get", return_value=_fake_get(CONTENT)):
        with pytest.raises(reg.ChecksumMismatchError) as exc:
            reg.ensure_model(KEY)
    assert "did not match" in str(exc.value) and "issues" in str(exc.value)
    assert isinstance(exc.value, FileNotFoundError)
    assert not reg.model_path(KEY).exists()
    assert not reg.model_path(KEY).with_name(reg.model_path(KEY).name + ".part").exists()


def test_every_registry_model_has_a_pinned_checksum():
    """A release must not ship models that cannot be verified."""
    missing = [k for k, m in reg.MODELS.items() if not m.get("sha256")]
    assert not missing, f"no sha256 pinned for: {missing}"
    for k, m in reg.MODELS.items():
        assert len(m["sha256"]) == 64 and int(m["sha256"], 16) >= 0, k


def test_verify_button_shows_results(monkeypatch):
    from videocraft.ui.dialogs.model_manager_dialog import ModelManagerDialog

    _install()
    _pin(monkeypatch, "0" * 64)
    dlg = ModelManagerDialog()
    row = list(reg.MODELS).index(KEY)

    dlg._on_verify_result(KEY, reg.MISMATCH, DIGEST)
    item = dlg.table.item(row, 2)
    assert "Corrupt" in item.text() and DIGEST in item.toolTip()

    _pin(monkeypatch, DIGEST)
    dlg._on_verify_result(KEY, reg.VERIFIED, DIGEST)
    assert "Verified" in dlg.table.item(row, 2).text()


def test_verify_worker_checks_installed_models(monkeypatch):
    from videocraft.ui.dialogs.model_manager_dialog import _VerifyWorker

    _install()
    _pin(monkeypatch, DIGEST)
    worker = _VerifyWorker([KEY])
    results = []
    worker.result.connect(lambda k, s, d: results.append((k, s, d)))
    worker.run()
    assert results == [(KEY, reg.VERIFIED, DIGEST)]
