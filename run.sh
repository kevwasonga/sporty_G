#!/usr/bin/env bash
# Sporty OTP Lab - quick launcher for macOS / Linux.
echo "============================================"
echo "  Sporty OTP Lab"
echo "============================================"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "** Python 3.10+ is required but was not found."
    echo "   Install it from https://www.python.org/downloads/"
    exit 1
fi

exec "$PY" run.py "$@"