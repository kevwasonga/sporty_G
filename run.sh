#!/usr/bin/env bash
# Sporty OTP Lab - quick launcher for macOS / Linux.
set -e
echo "============================================"
echo "  Sporty OTP Lab"
echo "============================================"

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
       && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "** Python 3.10+ is required but was not found."
    echo "   macOS:  install via 'brew install python' or https://www.python.org/downloads/"
    echo "   Linux:  install via your package manager, e.g. 'sudo apt install python3'"
    exit 1
fi

exec "$PY" run.py "$@"