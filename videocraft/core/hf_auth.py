"""Hugging Face access token — storage, validation, and safe header handling.

Most model downloads work without a token, but Hugging Face rate-limits
anonymous requests and some repositories are gated. A free read-only token
fixes both. The token is kept in its own file (not config.toml, which people
paste into bug reports) with owner-only permissions, and is only ever sent to
huggingface.co hosts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from videocraft.core.config import AppConfig

HF_JOIN_URL = "https://huggingface.co/join"
HF_TOKENS_URL = "https://huggingface.co/settings/tokens"
_WHOAMI_URL = "https://huggingface.co/api/whoami-v2"
_ENV_VARS = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")

# Statuses that mean "a token (or accepting a gated model's terms) may fix this".
AUTH_STATUSES = (401, 403, 429)


class DownloadAuthError(FileNotFoundError):
    """A model download was refused in a way a Hugging Face token may fix."""

    def __init__(self, status: int, url: str) -> None:
        self.status = status
        self.url = url
        super().__init__(
            f"Hugging Face refused the download (HTTP {status}). "
            "A free access token usually fixes this: open Settings → "
            "Hugging Face for step-by-step help."
        )


def token_path() -> Path:
    return AppConfig.platform_config_dir() / "hf_token"


def is_hf_url(url: str) -> bool:
    """True for huggingface.co and its subdomains (https only)."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "huggingface.co" or host.endswith(".huggingface.co"))


def saved_token() -> str | None:
    """The token saved in the app's own file (ignores the environment)."""
    try:
        return token_path().read_text().strip() or None
    except OSError:
        return None


def get_token() -> str | None:
    """The token from the environment (preferred) or the saved file."""
    for var in _ENV_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return saved_token()


def save_token(token: str) -> None:
    """Save the token with owner-only permissions; an empty token removes it."""
    token = token.strip()
    path = token_path()
    if not token:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with 0600 from the start so it is never briefly world-readable.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    if sys.platform != "win32":
        os.chmod(path, 0o600)


def auth_headers(url: str) -> dict[str, str]:
    """Authorization header for Hugging Face URLs when a token is set; else none."""
    token = get_token()
    if token and is_hf_url(url):
        return {"Authorization": f"Bearer {token}"}
    return {}


def validate_token(token: str) -> tuple[bool, str]:
    """Ask Hugging Face whether the token is valid. Returns (ok, message)."""
    token = token.strip()
    if not token:
        return False, "Paste a token first."
    try:
        resp = requests.get(
            _WHOAMI_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15
        )
    except requests.RequestException as e:
        return False, f"Could not reach Hugging Face: {e.__class__.__name__}"
    if resp.status_code == 200:
        name = (resp.json() or {}).get("name", "your account")
        return True, f"Token works — signed in as {name}."
    if resp.status_code in (401, 403):
        return False, "Hugging Face rejected this token. Check that you copied all of it."
    return False, f"Unexpected response from Hugging Face (HTTP {resp.status_code})."
