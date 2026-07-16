@echo off
setlocal
rem --- ClipAssembly launcher ---
rem Double-click to open the app. Or drag a video onto this file to open straight into Condense.
rem Keep this next to cs2_studio.py, condense_action.py and runescape_timeline.py.
cd /d "%~dp0"

if not exist "cs2_studio.py" (
  echo cs2_studio.py is not in this folder.
  echo Put ClipAssembly.bat in the SAME folder as cs2_studio.py, then try again.
  pause
  exit /b 1
)

python cs2_studio.py %*
if errorlevel 1 (
  echo.
  echo ClipAssembly could not start. Make sure Python is installed ^(python --version^).
  echo If you see nothing above, run  python cs2_studio.py  in this folder to see the error.
  pause
)
