@echo off
rem Windows launcher. The official python.org installer already bundles a
rem modern Tcl/Tk (unlike macOS's system Python, which needs the Homebrew
rem workaround in run.command), so no special interpreter path is needed here.
cd /d "%~dp0"
if not exist venv (
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
)
venv\Scripts\python main.py
