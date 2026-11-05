"""Portable paths for Python source and PyInstaller-frozen Windows EXE."""
from __future__ import annotations
import sys
from pathlib import Path


def app_dir() -> Path:
    """Keep mutable settings, WAVs and logs beside the standalone EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def driver_dir() -> Path:
    """Prefer external Airspy DLLs; also accept DLLs bundled with PyInstaller."""
    external = app_dir() / "drivers"
    if (external / "airspy.dll").is_file():
        return external
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", app_dir())) / "drivers"
        if (bundled / "airspy.dll").is_file():
            return bundled
    return external
