"""Locate bundled resources and developer data folders, from source or from a frozen build."""

import sys
from pathlib import Path

from platformdirs import user_config_path, user_log_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Folder holding bundled files: PyInstaller's unpack folder when frozen, else the project root."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return PROJECT_ROOT


def resource_path(relative: str) -> Path:
    return resource_root() / relative


def model_path(name: str) -> Path:
    path = resource_path(f"models/{name}")
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    return path


def clips_dir() -> Path:
    return PROJECT_ROOT / "clips"


def reports_dir() -> Path:
    return PROJECT_ROOT / "reports"


APP_NAME = "Hands Down"


def settings_path() -> Path:
    return user_config_path(APP_NAME, appauthor=False) / "settings.json"


def log_dir() -> Path:
    return user_log_path(APP_NAME, appauthor=False)
