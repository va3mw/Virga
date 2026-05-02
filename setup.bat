@echo off
setlocal

echo ============================================================
echo  Virga - Setup
echo ============================================================
echo.

:: Check for Python 3.12
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found.
    echo.
    echo Please download and install Python 3.12 from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to tick "Add Python to PATH" during install.
    echo Then re-run this script.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('py -3.12 --version') do echo Using %%v
echo.

:: Create virtual environment if it doesn't exist
if exist ".venv\Scripts\activate.bat" (
    echo Virtual environment already exists — skipping creation.
) else (
    echo Creating virtual environment...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Done.
)
echo.

:: Install / upgrade packages
echo Installing packages from requirements.txt...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Package installation failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Setup complete. Run Virga with:  run.bat
echo ============================================================
echo.
pause
endlocal
