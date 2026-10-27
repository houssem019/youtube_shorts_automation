@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo  Chess Shorts - video editor setup
echo ========================================
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Install the LTS version from https://nodejs.org
  echo then run setup_editor.bat again.
  pause
  exit /b 1
)

echo [1/4] Creating the editor's Python 3.12 environment...
python -m pip install --quiet --upgrade uv
if errorlevel 1 goto fail
if exist video_editor\.venv\Scripts\python.exe (
  echo Already exists, keeping it.
) else (
  python -m uv venv video_editor\.venv --python 3.12
  if errorlevel 1 goto fail
)

echo [2/4] Installing Python packages...
python -m uv pip install --python video_editor\.venv\Scripts\python.exe -r video_editor\requirements.txt
if errorlevel 1 goto fail

echo [3/4] Installing the video renderer (Remotion)...
pushd video_editor\studio
call npm install --no-fund --no-audit
if errorlevel 1 (popd & goto fail)
call npx remotion browser ensure
if errorlevel 1 (popd & goto fail)
popd

echo [4/4] Downloading the narrator voice and checking everything...
video_editor\.venv\Scripts\python.exe video_editor\setup_check.py
if errorlevel 1 goto fail

echo.
echo Setup finished.
pause
exit /b 0

:fail
echo.
echo Setup stopped because of the error above.
pause
exit /b 1
