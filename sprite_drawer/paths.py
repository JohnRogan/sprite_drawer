"""Default folders for file dialogs, resolved from the repo location (not the
working directory) so they are the same however the app is launched."""
from __future__ import annotations

import os

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES_DIR = os.path.join(REPO_DIR, "sprites")
SRC_IMG_DIR = os.path.join(REPO_DIR, "src_img")


def _ensure(path: str) -> str:
    """Return path, creating it if missing ("" lets Qt pick if that fails)."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return ""
    return path


def sprites_dir() -> str:
    """Default folder for sprite Open/Save dialogs."""
    return _ensure(SPRITES_DIR)


def src_img_dir() -> str:
    """Default folder for the reference-photo (underlay) dialog."""
    return _ensure(SRC_IMG_DIR)
