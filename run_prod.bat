@echo off
:: Production Environment Setup
set APP_ENV=prod

:: Email Configuration (SMTP)
:: Set these environment variables or configure them in your server environment
set EMAIL_BACKEND=smtp

:: --- SMTP SETTINGS ---
set SMTP_SERVER=smtp.gmail.com
set SMTP_PORT=587
set SENDER_EMAIL=porsche.tracker.app@gmail.com
set SENDER_PASSWORD=rmkljmigockhnujw
:: -------------------------------------------------------------

echo Starting Porsche Parts Tracker (Production Mode)...

:: Check if venv exists
if not exist venv (
    echo [ERROR] Virtual environment 'venv' not found.
    echo [i] Please run 'setup.bat' first to create the environment and install Python.
    pause
    exit /b 1
)

:: Activate venv
call venv\Scripts\activate

:: Run the application
python -m streamlit run app/main.py --server.port 8501 --server.address 0.0.0.0
pause
