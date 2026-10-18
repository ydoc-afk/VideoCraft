"""Download every model in the registry and print its SHA-256 and size.

Used by the "Model hashes" workflow (and runnable locally) to produce the
values pinned in videocraft/core/models_registry.py. Re-run it whenever a model
entry is added or an upstream file changes.

    python scripts/compute_model_hashes.py [--out model-hashes.json]

Set HF_TOKEN to authenticate Hugging Face downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

import requests

from videocraft.core.hf_auth import auth_headers
from videocraft.core.models_registry import MODELS


def hash_url(url: str) -> tuple[str, int]:
    sha = hashlib.sha256()
    size = 0
    with requests.get(url, stream=True, timeout=120, headers=auth_headers(url)) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=1 << 20):
            sha.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="model-hashes.json")
    args = parser.parse_args()

    results, failed = {}, False
    for key, meta in MODELS.items():
        url = meta["urls"][0]
        print(f"[{key}] {url}", flush=True)
        try:
            digest, size = hash_url(url)
        except requests.RequestException as e:
            print(f"  FAILED: {e}", flush=True)
            failed = True
            continue
        print(f"  sha256={digest}  size={size}", flush=True)
        results[key] = {"filename": meta["filename"], "sha256": digest, "size_bytes": size, "url": url}

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print("\n=== RESULT (paste into models_registry.py) ===")
    print(json.dumps({k: v["sha256"] for k, v in results.items()}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
