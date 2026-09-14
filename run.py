#!/usr/bin/env python3
"""Cross-platform launcher for the Sporty OTP Lab.

Usage:
    python run.py              # default port 8011
    python run.py --port 9000  # custom port

Sets up a virtualenv, installs dependencies + Playwright Chromium,
starts the API server (which also serves the built UI), and opens
your default browser.  Works on Windows, macOS, and Linux.
"""

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import venv
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "api"
UI_DIST = ROOT / "ui" / "dist"
VENV_DIR = ROOT / ".venv"
REQ_FILE = API_DIR / "requirements.txt"
ENV_EXAMPLE = API_DIR / ".env.example"
ENV_FILE = API_DIR / ".env"

IS_WINDOWS = platform.system() == "Windows"
PYTHON = "python" if IS_WINDOWS else "python3"


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_pip() -> list[str]:
    return [str(venv_python()), "-m", "pip"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def heading(msg: str) -> None:
    print(f"\n{'=' * 60}\n  {msg}\n{'=' * 60}")


def info(msg: str) -> None:
    print(f"  -> {msg}")


def warn(msg: str) -> None:
    print(f"  ** {msg}")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), **kw)


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def find_free_port(start: int) -> int:
    port = start
    while not port_is_free(port):
        port += 1
    return port


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def check_python() -> None:
    v = sys.version_info
    if v < (3, 10):
        print(f"ERROR: Python 3.10+ required, found {v.major}.{v.minor}.{v.micro}")
        sys.exit(1)
    info(f"Python {v.major}.{v.minor}.{v.micro} OK")


def ensure_venv() -> None:
    if not venv_python().exists():
        heading("Creating virtualenv")
        venv.create(str(VENV_DIR), with_pip=True)
        info(f"Created at {VENV_DIR}")
    else:
        info("Virtualenv already exists")

    # Some environments create venvs without pip (or pip gets removed later).
    # The launcher runs heavier on a broken venv than on a fresh one, so make
    # sure pip is present before we try to install anything.
    pip_check = run(
        [str(venv_python()), "-m", "pip", "--version"],
        capture_output=True, text=True,
    )
    if pip_check.returncode != 0:
        heading("Bootstrapping pip")
        bootstrap = run(
            [str(venv_python()), "-m", "ensurepip", "--upgrade", "--default-pip"],
            capture_output=True, text=True,
        )
        if bootstrap.returncode != 0:
            warn("ensurepip failed — rebuilding the virtualenv to restore pip")
            import shutil
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            venv.create(str(VENV_DIR), with_pip=True)
        info("pip is ready")


def install_deps() -> None:
    heading("Installing Python dependencies")
    run(venv_pip() + ["install", "--quiet", "-r", str(REQ_FILE)], check=True)
    info("Dependencies installed")


def install_playwright() -> None:
    heading("Installing Playwright Chromium browser")
    # `playwright install` is idempotent: it checks what's already in the
    # browser cache and skips downloads that are present, so running it every
    # start is cheap.
    run(
        [str(venv_python()), "-m", "playwright", "install", "chromium"],
        check=True,
    )
    info("Playwright Chromium installed")


def setup_env() -> None:
    if ENV_FILE.exists():
        info(".env already exists — skipping")
        return
    if not ENV_EXAMPLE.exists():
        warn("No .env.example found — skipping .env setup")
        return
    heading("Creating .env from .env.example")
    shutil.copy2(str(ENV_EXAMPLE), str(ENV_FILE))
    info(f"Copied {ENV_EXAMPLE.name} -> {ENV_FILE.name}")


def open_browser(url: str) -> None:
    import webbrowser
    heading("Opening browser")
    try:
        if webbrowser.open(url):
            info(f"Opened {url}")
            return
    except Exception as exc:
        warn(f"Could not open browser: {exc}")

    # Browser not available — print instructions
    warn("Could not auto-open a browser.")
    print(textwrap.dedent(f"""
        Please open one of these URLs manually:

          UI:    {url}
          API:   {url}/api/health
          Docs:  {url}/docs

        If you don't have a browser installed, download one:
          - Chrome:  https://www.google.com/chrome/
          - Firefox: https://www.mozilla.org/firefox/
          - Edge:    https://www.microsoft.com/edge (Windows built-in)
          - Safari:  https://www.apple.com/safari/ (macOS built-in)
    """))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Sporty OTP Lab launcher")
    parser.add_argument("--port", type=int, default=8011, help="API port (default: 8011)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser")
    args = parser.parse_args()

    port = find_free_port(args.port)
    if port != args.port:
        warn(f"Port {args.port} in use — using {port} instead")

    url = f"http://127.0.0.1:{port}"

    heading("Sporty OTP Lab")
    print(textwrap.dedent(f"""\
        Platform:  {platform.system()} {platform.machine()}
        Python:    {sys.version.split()[0]}
        Port:      {port}
        UI:        {url}
        API docs:  {url}/docs
    """))

    check_python()
    ensure_venv()
    install_deps()
    install_playwright()
    setup_env()

    # Check that the UI has been built
    if not (UI_DIST / "index.html").is_file():
        warn("ui/dist/index.html not found — the UI may not be built.")
        warn("Run: cd ui && npm install && npm run build")

    heading("Starting server")
    info(f"API + UI serving at {url}")

    # Build the uvicorn command
    uvicorn_cmd = [
        str(venv_python()), "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ]

    server = None
    try:
        server = subprocess.Popen(
            uvicorn_cmd,
            cwd=str(API_DIR),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        # Wait for server to be ready
        health_url = f"{url}/api/health"
        info(f"Waiting for server at {health_url} ...")
        if wait_for_server(health_url, timeout=30):
            info("Server is ready!")
        else:
            warn("Server may not be fully ready — try refreshing the page.")

        if not args.no_browser:
            open_browser(url)

        print(f"\n  Server running at {url}  (Ctrl+C to stop)\n")
        server.wait()

    except KeyboardInterrupt:
        print("\n\n  Shutting down...")
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        info("Stopped.")


if __name__ == "__main__":
    main()
