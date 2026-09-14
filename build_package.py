#!/usr/bin/env python3
"""Build a cross-platform ZIP distribution of the Sporty OTP Lab.

Usage:
    python build_package.py                  # sporty-otp-lab-<date>.zip

Creates a self-contained folder that a user on Windows / macOS / Linux can
extract and run with `run.bat` (Windows) or `python run.py` (the zip ships no
dependencies — the launcher installs them on first run).
"""

import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "api"
UI_SRC = ROOT / "ui"
UI_DIST = UI_SRC / "dist"

# Files copied verbatim into the distribution.
INCLUDE_PATHS = [
    "run.py",
    "run.bat",
    "run.sh",
    "README.md",
]

# api/ subtrees to exclude.
API_EXCLUDE = [
    "__pycache__",
    ".pytest_cache",
    "*.db",
    "*.sqlite",
    "test_*",
    "*test*",
    ".env",
]


def _matches(name: str, excludes: list[str]) -> bool:
    for pattern in excludes:
        if "*" in pattern:
            if pattern.startswith("*") and pattern.endswith("*"):
                if pattern[1:-1] in name:
                    return True
            elif pattern.endswith("*"):
                if name.startswith(pattern[:-1]):
                    return True
            elif pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
        elif name == pattern:  # exact name match (e.g. ".env" but not ".env.example")
            return True
    return False


def should_skip(rel: Path, excludes: list[str]) -> bool:
    return any(_matches(part, excludes) for part in rel.parts)


def collect(root: Path, excludes: list[str]) -> list[tuple[Path, Path]]:
    """Return (abs_path, rel_path_inside_zip_prefix) pairs."""
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        if should_skip(rel, excludes):
            continue
        out.append((p, rel))
    return out


def build() -> None:
    if not (UI_DIST / "index.html").is_file():
        print("ERROR: ui/dist is missing. Build it first:  cd ui && npm run build")
        sys.exit(1)

    zip_name = f"sporty-otp-lab-{date.today().isoformat()}.zip"
    zip_path = ROOT / zip_name
    print(f"Packaging -> {zip_path}")

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        base = "sporty-otp-lab"

        # Launchers + docs
        for name in INCLUDE_PATHS:
            src = ROOT / name
            if src.is_file():
                zf.write(str(src), f"{base}/{name}")
                print(f"  add {name}")

        # API backend
        for abs_path, rel in collect(API_DIR, API_EXCLUDE):
            zf.write(str(abs_path), f"{base}/api/{rel}")
            print(f"  add api/{rel}")

        # Pre-built UI
        for abs_path, rel in collect(UI_DIST, []):
            zf.write(str(abs_path), f"{base}/ui/dist/{rel}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"\nDone: {zip_path.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    build()