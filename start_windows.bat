@echo off
REM One click: starts ComfyUI (engine, private to this PC) + Easy Studio (the app, open to your home network).
cd /d "%~dp0"
set COMFY_URL=http://127.0.0.1:8188
set COMFY_DIR=%~dp0ComfyUI
set COMFY_PYTHON=%~dp0ComfyUI\venv\Scripts\python.exe
if "%EASY_STUDIO_HOST%"=="" set EASY_STUDIO_HOST=0.0.0.0
if "%EASY_STUDIO_PORT%"=="" set EASY_STUDIO_PORT=7860
if not exist outputs mkdir outputs
echo Starting ComfyUI in a separate (minimized) window...
start "ComfyUI engine - close to stop" /min "%~dp0ComfyUI\venv\Scripts\python.exe" "%~dp0ComfyUI\main.py" --listen 127.0.0.1 --port 8188
echo Waiting for ComfyUI to wake up (up to 2 minutes)...
powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8188/system_stats -TimeoutSec 2 | Out-Null; exit 0}catch{Start-Sleep 1}}; exit 1"
if errorlevel 1 echo ComfyUI did not answer. Look at the "ComfyUI engine" window for the error.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do set IP=%%a
set IP=%IP: =%
echo.
echo ==============================================================
echo  Easy Studio is starting.
echo    On this PC:        http://127.0.0.1:%EASY_STUDIO_PORT%
echo    From your MacBook: http://%IP%:%EASY_STUDIO_PORT%
echo  Other devices will be asked for a password: it is shown below and saved in outputs\password.txt
echo  If Windows asks about the firewall, tick "Private networks" and click Allow.
echo  Close this window to stop the app (close the ComfyUI window too).
echo ==============================================================
start "" http://127.0.0.1:%EASY_STUDIO_PORT%
"%~dp0.venv\Scripts\python.exe" "%~dp0app\server.py"
if "%EASY_STUDIO_NO_PAUSE%"=="1" goto :eof
pause
