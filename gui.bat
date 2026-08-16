@echo off
REM Launch the model tester GUI. Double-click, or pass args: gui.bat --port 7861
REM
REM Deliberately NOT `uv run`: that syncs the environment first, and syncing
REM uninstalls the locally-installed CUDA torch (see the warning in
REM pyproject.toml), leaving the GUI on CPU. Plain python uses the env as-is.

cd /d "%~dp0"

if not exist "src\gui\app.py" (
    echo src\gui\app.py not found.
    echo The GUI lives on the feature/gui branch. Switch to it first:
    echo     git checkout feature/gui
    pause
    exit /b 1
)

set PYTHONPATH=src
python -m gui.app %*

REM Keep the window open so a traceback is readable when double-clicked.
if errorlevel 1 pause
