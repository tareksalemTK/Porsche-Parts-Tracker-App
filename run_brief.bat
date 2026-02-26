@echo off
:: Execution Wrapper for Morning Brief Scheduler
set APP_ENV=prod

:: Email Configuration (SMTP)
set EMAIL_BACKEND=smtp

:: --- SMTP SETTINGS ---
set SMTP_SERVER=smtp.office365.com
set SMTP_PORT=587
set SENDER_EMAIL=tmaher@porscheleb.com
set SENDER_PASSWORD=tottlf00722
:: -------------------------------------------------------------

echo Executing Morning Brief Script...

:: Check if venv exists
if not exist venv (
    echo [ERROR] Virtual environment 'venv' not found.
    exit /b 1
)

:: Activate venv
call venv\Scripts\activate

:: Run the morning brief script
python app/run_brief.py
