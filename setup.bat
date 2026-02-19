@echo off
echo ==========================================
echo    Porsche Parts Tracker - Setup Script
echo ==========================================

:: Check for Python using 'py' launcher
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python launcher 'py' not found.
    echo Please install Python from https://www.python.org/downloads/
    echo ensuring you check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [i] Python launcher found.
echo.

:: Create Virtual Environment
if not exist venv (
    echo [i] Creating virtual environment 'venv'...
    py -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [i] Virtual environment 'venv' already exists.
)

:: Activate and Install Requirements
echo [i] Activating environment and installing dependencies...
call venv\Scripts\activate

echo [i] Upgrading pip...
python -m pip install --upgrade pip

if exist requirements.txt (
    echo [i] Installing requirements from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [WARNING] requirements.txt not found! Skipping dependency installation.
)

echo.
echo ==========================================
echo    Setup Complete!
echo    You can now run 'run_prod.bat'
echo ==========================================
pause
