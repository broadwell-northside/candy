# Easy Studio installer for Windows 11 + NVIDIA RTX PRO 6000.
# Run by double-clicking install_windows.bat (in the main folder). Takes 1-3 hours, mostly downloading (model downloads ~139 GB).
param([switch]$NoModels)
$ErrorActionPreference = "Continue"   # native tools print progress to stderr; we check exit codes instead
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $what" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 } }
$Root  = Split-Path -Parent $PSScriptRoot
$Comfy = Join-Path $Root "ComfyUI"
function Say($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }
function Need($exe, $wingetId) {
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
    Write-Host "Installing $wingetId ..."
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
    Refresh-Path
  }
}

Say "Step 1/5: tools (Git, Python 3.13, ffmpeg)"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Write-Host "winget is missing. Open Microsoft Store, install 'App Installer', then run this again." -ForegroundColor Red; exit 1
}
Need git "Git.Git"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Need python "Python.Python.3.13" }
Need ffmpeg "Gyan.FFmpeg"
Refresh-Path
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
} else {
  Write-Warning "NVIDIA driver not found. Install the latest RTX PRO driver from nvidia.com, reboot, run again."
}
$Py = $null; $PyArgs = @()
try { & py -3.13 --version *> $null; if ($LASTEXITCODE -eq 0) { $Py = "py"; $PyArgs = @("-3.13") } } catch {}
if (-not $Py) { $Py = "python" }

Say "Step 2/5: ComfyUI (the engine)"
if (-not (Test-Path (Join-Path $Comfy ".git"))) { git clone https://github.com/Comfy-Org/ComfyUI.git $Comfy; Check "downloading ComfyUI" }
else { git -C $Comfy pull --ff-only }
$CPy = Join-Path $Comfy "venv\Scripts\python.exe"
if (-not (Test-Path $CPy)) { & $Py @PyArgs -m venv (Join-Path $Comfy "venv") }
& $CPy -m pip install --upgrade pip wheel
& $CPy -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { & $CPy -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128; Check "installing PyTorch" }
& $CPy -m pip install -r (Join-Path $Comfy "requirements.txt"); Check "installing ComfyUI requirements"
# No custom nodes are required: the bundled workflows use only built-in ComfyUI nodes.

Say "Step 3/5: Easy Studio app"
$APy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $APy)) { & $Py @PyArgs -m venv (Join-Path $Root ".venv") }
& $APy -m pip install --upgrade pip
& $APy -m pip install -r (Join-Path $Root "requirements.txt"); Check "installing Easy Studio requirements"

Say "Step 4/5: model files (~139 GB, resumable; just run again if it stops)"
$free = [math]::Round((Get-PSDrive ((Get-Item $Root).PSDrive.Name)).Free/1GB); Write-Host "Free disk space: $free GB (need about 150 GB)"
if (-not $NoModels) { & $APy (Join-Path $Root "install\download_models.py") --comfy $Comfy --what all }
else { Write-Host "Skipped model downloads." }

Say "Step 5/5: quick self-test (no GPU needed)"
& $APy (Join-Path $Root "tests\run_tests.py")

Say "Done! Double-click start_windows.bat to start Easy Studio."
