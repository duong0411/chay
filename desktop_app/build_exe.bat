@echo off
setlocal
cd /d "%~dp0"

echo === Safety Remote Desktop · build EXE ===
py -3.12 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist models\yolov8n_fire.xml (
  echo [info] Chua co OpenVINO model — dang tai / export...
  py -3.12 ai\download_model.py
)

py -3.12 -m PyInstaller --noconfirm --clean safety_desktop.spec
if errorlevel 1 exit /b 1

echo.
echo DONE: dist\SafetyRemoteDesktop.exe
echo Gui kem thu muc models\ (neu model nam ngoai EXE) cho khach hang.
endlocal
