# Deployment Guide: PCL Parts Reservation Tracker

## Prerequisites
1.  **Python 3.8+** installed (SQLite is built-in to Python, no separate DB installation needed).
2.  **Git** installed (optional, for cloning).
3.  Network port **8501** (default) open on firewall.
4.  **SMTP Credentials** (Server, Port, Email, Password) for notifications.

## 1. Installation

### Windows & Linux
1.  Copy project files to server.
2.  Open terminal/command prompt in project root.
3.  Create virtual environment:
    ```bash
    python -m venv venv
    ```
4.  Activate environment:
    *   **Windows**: `venv\Scripts\activate`
    *   **Linux**: `source venv/bin/activate`
5.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 2. Windows Server Deployment

### Manual Run
Double-click `run_prod.bat`.

### Auto-Start (Task Scheduler)
1.  Open **Task Scheduler**.
2.  Create Basic Task -> "Start a Program".
3.  Program/Script: `path\to\run_prod.bat`.
4.  Trigger: "When computer starts".
5.  Properties: Check "Run whether user is logged on or not".

## 3. Linux Server Deployment

### Systemd Service
1.  Create service file: `sudo nano /etc/systemd/system/porsche_app.service`
    ```ini
    [Unit]
    Description=Porsche Parts Tracker
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/path/to/Porsche_BI_Progect
    Environment="APP_ENV=prod"

    # SMTP Config (Uncomment and set)
    # Environment="SMTP_SERVER=smtp.office365.com"
    # Environment="SMTP_PORT=587"
    # Environment="SENDER_EMAIL=parts.tracker@your-dealership.com"
    # Environment="SENDER_PASSWORD=your-secure-password"
    ExecStart=/path/to/Porsche_BI_Progect/venv/bin/python -m streamlit run app/main.py --server.port 8501
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
2.  Enable and start:
    ```bash
    sudo systemctl enable porsche_app
    sudo systemctl start porsche_app
    ```

## 4. Network Access

Access via browser:
`http://<SERVER_IP>:8501`

## 5. Email Configuration (Crucial)

To enable the new **Porsche Premium Email Notifications** in production (Outlook/Gmail), you must configure real SMTP credentials.

### A. Windows Server (Batch File)
Right-click `run_prod.bat` -> **Edit**, and uncomment/fill in your email server details:

```bat
:: --- SMTP SETTINGS (Uncomment and set these for production) ---
set SMTP_SERVER=smtp.office365.com
set SMTP_PORT=587
set SENDER_EMAIL=parts.tracker@your-dealership.com
set SENDER_PASSWORD=your-secure-password
:: -------------------------------------------------------------
```

### B. Linux Server (Systemd)
Edit the service file: `sudo nano /etc/systemd/system/porsche_app.service`
Add environment variables under `[Service]`:

```ini
Environment="SMTP_SERVER=smtp.office365.com"
Environment="SMTP_PORT=587"
Environment="SENDER_EMAIL=parts.tracker@your-dealership.com"
Environment="SENDER_PASSWORD=your-secure-password"
```
Reload daemon: `sudo systemctl daemon-reload` & `sudo systemctl restart porsche_app`

### B. Logo & Branding Compatibility
- The app sends emails with the **Porsche Logo** embedded.
- **Microsof Outlook Note**: Some desktop versions of Outlook may block images by default. 
    - *Fallback*: We have initiated a "Text Fallback" so if the image is blocked, a bold **PORSCHE** header appears, ensuring the email always looks professional.
    - *Action*: In Outlook, you may need to right-click the banner and select "Download Pictures" to see the logo.

## 6. Admin & User Admin
1.  **Create Admin User**: 
    - Log in as the default admin on first run.
    - Go to **User Management**.
2.  **Assign Real Emails**:
    - Edit or Create users for your Service Advisors ("SADV").
    - **Crucial**: Ensure you enter their **Real Email Addresses**. If the email field is blank, the system will not send notifications to that advisor.
