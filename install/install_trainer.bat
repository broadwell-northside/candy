@echo off
REM Installs the character trainer (ostris/ai-toolkit, MIT licence) into trainer\ai-toolkit with its own Python.
REM Needs git and Python 3.10-3.12 on PATH, and an NVIDIA driver. About 10 GB including torch.
cd /d "%~dp0.."
if not exist trainer mkdir trainer
if not exist trainer\ai-toolkit\.git (
  git clone https://github.com/ostris/ai-toolkit.git trainer\ai-toolkit || goto :fail
) else (
  git -C trainer\ai-toolkit pull --ff-only
)
git -C trainer\ai-toolkit submodule update --init --recursive
if not exist trainer\ai-toolkit\venv python -m venv trainer\ai-toolkit\venv || goto :fail
trainer\ai-toolkit\venv\Scripts\python.exe -m pip install --upgrade pip wheel
trainer\ai-toolkit\venv\Scripts\pip.exe install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 || goto :fail
trainer\ai-toolkit\venv\Scripts\pip.exe install -r trainer\ai-toolkit\requirements.txt || goto :fail
echo.
echo Trainer installed. Restart Easy Studio; the Train my character tab is ready.
pause
exit /b 0
:fail
echo Something went wrong (see above). Check that git and Python are installed and on PATH.
pause
exit /b 1
