@echo off
echo ========================================
echo Chess YouTube Automation
echo ========================================
echo.

rem Optional arguments for scheduled runs: run_chess_automation.bat [game link/ID or ""] [short^|long]
set "GAME=%~1"
set "FORMAT=%~2"

rem A game given without a format (older scheduled runs) makes a Short, without asking.
if not defined FORMAT if "%~1"=="" (
  echo What do you want to make?
  echo   [1] Short ^(vertical, 45-50 s^)
  echo   [2] Long video ^(16:9, 5-10 min^)
  set /p "FORMAT=Choice (Enter = Short): "
)
if "%FORMAT%"=="2" set "FORMAT=long"
if /i "%FORMAT%"=="l" set "FORMAT=long"
if /i not "%FORMAT%"=="long" set "FORMAT=short"
echo.

if "%~1"=="" (
  echo Paste a chess.com game link or ID to use that game,
  echo or just press Enter for a random game that has no %FORMAT% video yet.
  set /p "GAME=Game: "
)
echo.

echo Starting automation ^(%FORMAT%^)...
if "%FORMAT%"=="long" echo A long video takes 1-2 hours to render. Leave this window open.
echo.

if defined GAME (
  python main.py --format %FORMAT% "%GAME%"
) else (
  python main.py --format %FORMAT%
)

echo.
echo ========================================
echo Automation completed!
echo ========================================
echo.
pause
