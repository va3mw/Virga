@echo off
setlocal

echo ============================================================
echo  Virga - Setup
echo ============================================================
echo.

:: ── Check for a default Python and warn if it is pre-release ────────────
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set DEFAULT_PY=%%v
    for /f "tokens=1,2 delims=." %%a in ("!DEFAULT_PY!") do (
        set PY_MAJOR=%%a
        set PY_MINOR=%%b
    )
)

:: Enable delayed expansion for the version check above
setlocal enabledelayedexpansion

python --version >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set DEFAULT_PY=%%v
    for /f "tokens=1,2 delims=." %%a in ("!DEFAULT_PY!") do (
        set PY_MAJOR=%%a
        set PY_MINOR=%%b
    )
    if !PY_MINOR! GEQ 13 (
        echo WARNING: Your default Python is !DEFAULT_PY!
        echo Python 3.13 and later are not yet fully supported by all
        echo audio packages Virga needs ^(sounddevice / cffi^).
        echo This setup will use Python 3.12 specifically instead.
        echo.
    )
)

:: ── Require Python 3.12 ─────────────────────────────────────────────────
py -3.12 --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.12 not found.
    echo.
    echo Virga requires Python 3.12 due to audio library compatibility.
    echo Python 3.13+ is not yet supported by the sounddevice package.
    echo.
    echo Install Python 3.12 using one of these methods:
    echo.
    echo   Option A - winget ^(run in this terminal^):
    echo     winget install Python.Python.3.12
    echo.
    echo   Option B - download manually:
    echo     https://www.python.org/downloads/
    echo     ^> Select Python 3.12.x ^> Windows installer ^(64-bit^)
    echo     ^> Tick "Add Python to PATH" on the first screen
    echo.
    echo Then re-run this script.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('py -3.12 --version') do echo Using %%v
echo.

:: ── Create virtual environment ───────────────────────────────────────────
if exist ".venv\Scripts\activate.bat" (
    echo Virtual environment already exists -- skipping creation.
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

:: ── Install packages ─────────────────────────────────────────────────────
echo Installing packages from requirements.txt...
echo ^(This may take a minute on first run^)
echo.
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Package installation failed.
    echo.
    echo Common causes:
    echo   - No internet connection
    echo   - Firewall blocking pip
    echo   - Disk space low
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Setup complete.
echo  Run Virga any time by double-clicking run.bat
echo ============================================================
echo.
pause
endlocal
