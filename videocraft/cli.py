"""Command-line entry point: `videocraft` (GUI), `videocraft setup`, `--version`."""

from __future__ import annotations

import argparse
import sys

from videocraft import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="videocraft",
        description="VideoCraft — AI video enhancement. Run without arguments to open the app.",
    )
    parser.add_argument("--version", action="version", version=f"VideoCraft {__version__}")
    sub = parser.add_subparsers(dest="command")

    setup = sub.add_parser(
        "setup",
        help="install the optional AI packages (PyTorch, Real-ESRGAN, …) for this GPU",
        description=(
            "Install the packages the AI tools need into the current Python "
            "environment and check that they work."
        ),
    )
    setup.add_argument(
        "--gpu", choices=["auto", "nvidia", "cpu"], default="auto",
        help="which PyTorch build to install (default: detect an NVIDIA GPU)",
    )
    setup.add_argument(
        "--torch-index-url", metavar="URL",
        help="install PyTorch from this package index instead (e.g. a ROCm build)",
    )
    setup.add_argument(
        "--dry-run", action="store_true",
        help="print the commands that would run, without running them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "setup":
        from videocraft.installer import run_setup

        return run_setup(
            gpu=args.gpu, torch_index_url=args.torch_index_url, dry_run=args.dry_run
        )

    from videocraft.main import main as gui_main

    sys.argv = sys.argv[:1]  # keep Qt from parsing our arguments
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
