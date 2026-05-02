@echo off
setlocal

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found — running setup first...
    echo.
    call setup.bat
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat

for /f "tokens=*" %%v in ('python --version') do echo Running on %%v
echo.

python main.py

if errorlevel 1 (
    echo.
    echo Virga exited with an error ^(code %errorlevel%^).
    pause
)
endlocal
