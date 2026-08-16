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

REM Call the venv interpreter by path instead of relying on `python` from PATH.
REM A plain cmd.exe window has no venv on PATH and picks up miniconda or the
REM system Python, neither of which has this project's dependencies.
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo Virtualenv not found at %PY%
    echo Create it with:  uv venv
    pause
    exit /b 1
)

set PYTHONPATH=src
"%PY%" -m gui.app %*

REM Keep the window open so a traceback is readable when double-clicked.
if errorlevel 1 pause
