@echo off
setlocal

:: Auto-run setup if venv is missing
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found — running setup first...
    echo.
    call setup.bat
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat
python main.py
endlocal
