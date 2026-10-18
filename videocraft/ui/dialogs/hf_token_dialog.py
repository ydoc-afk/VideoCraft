"""Step-by-step help for getting and saving a Hugging Face access token."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from videocraft.core import hf_auth
from videocraft.core.theme import mark_hint

_STEPS_HTML = f"""
<ol>
  <li><b>Create a free account</b> at <a href="{hf_auth.HF_JOIN_URL}">huggingface.co/join</a>
      (or sign in if you already have one).</li>
  <li>Open <a href="{hf_auth.HF_TOKENS_URL}">huggingface.co/settings/tokens</a> and click
      <b>Create new token</b>.</li>
  <li>Choose the <b>Read</b> type, name it <i>VideoCraft</i>, and click <b>Create token</b>.</li>
  <li><b>Copy the token</b> (it starts with <code>hf_</code>). Hugging Face only shows it once.</li>
  <li><b>Paste it below</b>, click <b>Test token</b>, then <b>Save token</b>.</li>
</ol>
"""

_REASONS = {
    429: "Hugging Face is limiting anonymous downloads right now. A free token lifts that limit.",
    401: "Hugging Face needs you to be signed in to download this model.",
    403: (
        "Hugging Face refused the download. Add a token below, and if it still fails, open the "
        "model's page on huggingface.co while signed in and accept its terms."
    ),
}


class _ValidateWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def run(self) -> None:
        ok, message = hf_auth.validate_token(self._token)
        self.done.emit(ok, message)


class HFTokenDialog(QDialog):
    """Explains how to get a token, tests it, and saves it (owner-only file)."""

    def __init__(self, parent=None, status: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hugging Face access token")
        self.setMinimumWidth(520)
        self._worker: _ValidateWorker | None = None
        self._setup_ui(status)

    def _setup_ui(self, status: int | None) -> None:
        layout = QVBoxLayout(self)

        if status in _REASONS:
            reason = QLabel(_REASONS[status])
            reason.setWordWrap(True)
            layout.addWidget(reason)

        intro = QLabel(
            "A free Hugging Face account and a read-only access token are all VideoCraft needs "
            "to download models reliably. The token is stored only on this computer and is sent "
            "only to huggingface.co."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QLabel(_STEPS_HTML)
        steps.setWordWrap(True)
        steps.setOpenExternalLinks(True)
        layout.addWidget(steps)

        row = QHBoxLayout()
        self.le_token = QLineEdit()
        self.le_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_token.setPlaceholderText("hf_…")
        self.le_token.setText(hf_auth.saved_token() or "")
        row.addWidget(self.le_token, 1)
        self.chk_show = QCheckBox("Show")
        self.chk_show.toggled.connect(
            lambda on: self.le_token.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        row.addWidget(self.chk_show)
        layout.addLayout(row)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        mark_hint(self.lbl_status, True)
        layout.addWidget(self.lbl_status)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.btn_test = QPushButton("Test token")
        self.btn_test.clicked.connect(self._on_test)
        buttons.addWidget(self.btn_test)
        self.btn_save = QPushButton("Save token")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save)
        buttons.addWidget(self.btn_save)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

    def _on_test(self) -> None:
        self.btn_test.setEnabled(False)
        self.lbl_status.setText("Checking…")
        self._worker = _ValidateWorker(self.le_token.text())
        self._worker.done.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        self.lbl_status.setText(("✓ " if ok else "✗ ") + message)
        self.btn_test.setEnabled(True)

    def _on_save(self) -> None:
        token = self.le_token.text().strip()
        if not token:
            self.lbl_status.setText("Paste a token first (or press Cancel).")
            return
        hf_auth.save_token(token)
        self.accept()

    def done(self, result: int) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(16000)
        super().done(result)
