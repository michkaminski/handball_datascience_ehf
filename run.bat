@echo off
setlocal
cd /d "%~dp0"
echo EHF: http://127.0.0.1:5151
if exist "..\.venv\Scripts\python.exe" (
    "..\.venv\Scripts\python.exe" "app.py"
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "app.py"
) else (
    python "app.py"
)
endlocal
