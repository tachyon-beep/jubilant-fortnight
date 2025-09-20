"""Utility script to download Granite Guardian moderation weights.

Usage:
    python -m great_work.tools.download_guardian_model --target ./models/guardian

The script relies on `huggingface_hub`. Install it with `pip install huggingface_hub`
before running. Authentication is handled via the standard Hugging Face token
mechanisms (`HUGGINGFACE_TOKEN` environment variable or cached login).

No network calls are performed unless you execute the script. This file exists so
we do not keep large model weights in the repository.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_dependencies() -> None:
    try:
        import huggingface_hub  # noqa: F401
    except ImportError as exc:  # pragma: no cover - dependency is optional for runtime
        raise SystemExit(
            "huggingface_hub is not installed. Install it with 'pip install huggingface_hub'"
        ) from exc


def download_model(model_id: str, revision: Optional[str], target: Path, token: Optional[str]) -> Path:
    from huggingface_hub import snapshot_download

    logger.info("Downloading %s to %s", model_id, target)
    target.mkdir(parents=True, exist_ok=True)

    snapshot_path = snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=target,
        local_dir_use_symlinks=False,
        token=token,
        resume_download=True,
    )
    logger.info("Model snapshot available at %s", snapshot_path)
    return Path(snapshot_path)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Granite Guardian moderation model")
    parser.add_argument(
        "--model-id",
        default="ibm-granite/granite-guardian-3.2-3b-a800m",
        help=(
            "Hugging Face model repository ID (default: ibm-granite/granite-guardian-3.2-3b-a800m)"
        ),
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional git revision or tag to download (default: latest)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Directory where the model snapshot should be stored",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Optional Hugging Face access token. If omitted, defaults to environment/CLI login",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ensure_dependencies()
    try:
        download_model(args.model_id, args.revision, args.target, args.token)
    except Exception as exc:  # pragma: no cover - network errors are contextual
        logger.error("Failed to download moderation model: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main(sys.argv[1:])
