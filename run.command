#!/bin/bash
# Uses the bundled venv (Homebrew Python + modern Tcl/Tk 9.x) rather than the
# system python3, which bundles an ancient Tcl/Tk 8.5 known to render blank
# windows on modern macOS.
cd "$(dirname "$0")"
if [ ! -d venv ]; then
    /opt/homebrew/bin/python3.13 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi
./venv/bin/python3 main.py
