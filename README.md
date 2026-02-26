# PCL Parts Reservation Tracker

> A Streamlit-based internal web application for Porsche Center warehouse teams to track, manage, and receive notifications on special-order parts — from initial order through back order, shipment, and customer pickup.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Project Structure](#project-structure)
3. [Installation & Setup](#installation--setup)
4. [Running the Application](#running-the-application)
5. [User Roles & Permissions](#user-roles--permissions)
6. [Features Overview](#features-overview)
7. [Email Notifications](#email-notifications)
8. [Database Structure](#database-structure)
9. [Backup & Restore](#backup--restore)
10. [Deployment Guide](#deployment-guide)

---

## System Requirements

### Operating System
| | Version |
|---|---|
| **Recommended** | Windows 10 Pro / Windows 11 Pro (64-bit) |
| **Minimum** | Windows 10 (Build 1903 or later, 64-bit) |
| **Server Option** | Windows Server 2019 / 2022 (for always-on deployment via Task Scheduler) |

> The application ships with `run_prod.bat` and `setup.bat` and is purpose-built for Windows deployment.

---

### RAM
| Scenario | Minimum | Recommended |
|---|---|---|
| Single user (local machine) | 4 GB | **8 GB** |
| Multi-user (dealership server, 5–10 concurrent users) | 8 GB | **16 GB** |

> **Why more than a basic web app?**
> - Multiple pandas DataFrames are held in memory simultaneously (parts table, archived items, shipment data, analytics, notifications)
> - The analytics engine builds pivot tables and bar charts from SQLite on every page refresh
> - Excel file parsing via `openpyxl` loads entire `.xlsx` files into RAM during uploads (On Order / Back Order / Invoiced)
> - `bcrypt` password hashing on every login is intentionally memory- and CPU-intensive by security design
> - The Ledger search joins remarks and parts tables and builds a full event timeline DataFrame per query

---

### CPU
| | Specification |
|---|---|
| **Minimum** | Dual-core, 2.0 GHz (Intel Core i3 / AMD Ryzen 3) |
| **Recommended** | Quad-core, 2.5 GHz+ (Intel Core i5 / AMD Ryzen 5) |

> `bcrypt` password hashing is CPU-intensive by design. The smart order-matching algorithm in the upload pipeline also runs regex normalization and fuzzy numeric matching across all part records on every Excel upload — this is a CPU-bound operation.

---

### Storage (HDD / SSD)

| Component | Size |
|---|---|
| Python 3.10+ Runtime | ~100 MB |
| Virtual Environment + Packages (`streamlit`, `pandas`, `openpyxl`, `bcrypt`, `schedule`) | ~350 MB |
| Application source code | ~5 MB |
| Porsche branding assets (logos embedded in emails + UI) | ~5 MB |
| SQLite database — `porsche_parts_prod.db` (parts, remarks, notifications, audit logs, backups registry) | 50 MB – 2 GB *(grows with data over time)* |
| Database backup copies *(each backup = full copy of the `.db` file)* | 50 MB – 2 GB *per backup* |
| **Total Minimum (fresh install)** | **~1 GB** |
| **Recommended Free Space** | **10 GB** *(covers multiple backup versions and years of operational data)* |

> ⚠️ **SSD strongly recommended over HDD** — the application makes frequent small SQLite read/write operations (remarks, notifications, status updates, audit log appends) and parses Excel files. An SSD dramatically improves responsiveness in a multi-user environment.

---

### Additional Requirements

| Requirement | Detail |
|---|---|
| **Python Version** | 3.10+ recommended (3.8 absolute minimum) |
| **Network Port** | Port **8501** must be open on the firewall for multi-user browser access |
| **Browser** | Google Chrome, Microsoft Edge, or Firefox (latest version) |
| **SMTP Access** | Required for email notifications — `smtp.office365.com` port 587 (Microsoft 365 / Outlook) |
| **Internet** | Only required during initial setup to download Python packages |
| **Microsoft Excel** | NOT required on the server — `.xlsx` files are read directly by the app via `openpyxl` |

---

## Project Structure

```
Porsche Parts Tracker App/
│
├── app/
│   ├── main.py          # Core Streamlit application (UI, routing, all page logic)
│   ├── db.py            # All database operations (SQLite via sqlite3 + pandas)
│   ├── mailer.py        # HTML email engine (Porsche-branded notifications)
│   ├── utils.py         # Excel parsing, order normalization, aging calculations
│   ├── scheduler.py     # Background job scheduler (stale stock alerts)
│   └── config.py        # Environment config (dev/prod paths, DB name)
│
├── assets/              # Porsche branding images (logo used in UI and emails)
├── data/                # SQLite database files (auto-created on first run)
│   ├── porsche_parts.db       # Development database
│   └── porsche_parts_prod.db  # Production database
│
├── setup.bat            # One-click setup: creates venv and installs all dependencies
├── run_prod.bat         # One-click production launcher (sets APP_ENV=prod)
├── requirements.txt     # Python package dependencies
└── deployment.md        # Detailed server deployment guide
```

---

## Installation & Setup

### Step 1 — Prerequisites
- Download and install **Python 3.10+** from [python.org](https://www.python.org/downloads/)
- ✅ During installation, check **"Add Python to PATH"**

### Step 2 — Run Setup Script
Double-click `setup.bat` in the project root. This will:
1. Verify Python is installed
2. Create a Python virtual environment (`venv/`)
3. Upgrade `pip`
4. Install all dependencies from `requirements.txt`

### Step 3 — Configure SMTP (for Email Notifications)
Open `run_prod.bat` in a text editor and fill in your SMTP credentials:

```bat
set SMTP_SERVER=smtp.office365.com
set SMTP_PORT=587
set SENDER_EMAIL=parts.tracker@your-dealership.com
set SENDER_PASSWORD=your-secure-password
```

---

## Running the Application

### Production (Recommended)
Double-click `run_prod.bat`

This sets `APP_ENV=prod`, which:
- Uses `porsche_parts_prod.db` as the database
- Sets `DEBUG=False`
- Launches Streamlit on port 8501

### Access via Browser
Once running, open any browser on the network and navigate to:
```
http://<SERVER_IP>:8501
```

### Default Admin Credentials
| Username | Password |
|---|---|
| `admin` | `admin` |
| `sadmin` | `sadmin` |

> ⚠️ **Change these passwords immediately after first login.**

---

## User Roles & Permissions

| Role | Access Level | Can Post/Archive | Can Manage Users |
|---|---|---|---|
| `super_admin` | Everything + Executive Dashboard | ✅ | ✅ |
| `admin` | Everything | ✅ | ❌ |
| `PRTADV` | All advisors except OTC | ✅ | ❌ |
| `A` | All advisors except OTC | ❌ | ❌ |
| `Read Only` | All advisors (view only) | ❌ | ❌ |
| `SaMnagment` | EMA, EMB, EMC groups only | ❌ | ❌ |
| `OTC` | OTC parts only | ✅ | ❌ |
| `ServiceADV` | Own advisor code only | ❌ | ❌ |

> Users can hold **multiple roles** simultaneously (stored as comma-separated values, e.g. `admin,super_admin`).

---

## Features Overview

### 📁 Data Upload (Admin)
- **On Order**: Upload Excel file → assigns parts to a selected Service Advisor → sends email notification
- **Back Order**: Upload Excel file with a custom Back Order start date → smart-matches existing parts by order number (fuzzy numeric matching) → updates status + triggers email
- **Invoiced / Shipment**:
  1. Upload to mark items as *In Transit* (with ETA)
  2. Review & receive stock with editable quantities
  3. Overview panel to manage ETA updates and send advisor notifications

### 📊 Executive Dashboard (Super Admin only)
- Total Active Orders metric
- Stock Awaiting Pickup metric
- Advisor Workload stacked bar chart
- Problem Items table (parts aging > 10 days in Back Order or Received status)
- Top Ordered Parts chart
- Backup & Restore controls

### 📋 Main Dashboard (All Users)
- Live parts table filtered by user role and advisor code
- Single-row selection with contextual actions
- Color-coded aging indicators (green ≤ 3 days, yellow ≤ 9 days, red > 10 days)
- Filter panel across any column with one-click clear
- Excel export of all visible data

### 📖 Ledger / Item History
- Full audit trail per part: every upload, status change, remark, posting event
- Searchable by Item No, Order No, or Customer Name
- Sorted by most recent event

### 🔔 Notifications
- In-app notification bell showing unread system events
- Per-advisor targeting and global broadcasts
- Dismissable per item or bulk-cleared

---

## Email Notifications

The application sends branded **Porsche HTML emails** (with embedded logo) via SMTP for:

| Trigger | Recipients |
|---|---|
| New On Order file uploaded | All users assigned to that Service Advisor |
| Parts moved to Back Order | Affected advisor's users |
| Parts marked In Transit (shipment upload) | Affected advisor's users |
| Parts received into stock | Affected advisor's users |
| ETA updated on a shipment | Affected advisor's users |
| Items Posted / Archived | Affected advisor's users |
| Stale stock warning (> 7 days Received) | Relevant service advisor users |

> Emails include: Item No, Description, Status, Customer Name, Document No, Customer No, and aging duration.

---

## Database Structure

The application uses **SQLite** (no separate database server required). The database is auto-created and auto-migrated on first run.

### Tables

| Table | Purpose |
|---|---|
| `users` | Login credentials, roles (`user_type`), advisor codes, emails |
| `parts` | Core parts tracking — 16 business columns + audit fields |
| `item_remarks` | Per-part remarks with follow-up and reminder dates, read receipts |
| `notifications` | In-app notification messages with targeting (user/advisor/type) |
| `database_backups` | Registry of backup restore points (metadata + file path) |

### Parts Lifecycle / Statuses

```
On Order → Back Order → In Transit → Received → [Posted/Archived]
                                  ↘ Partially Received → Reordered → In Transit
```

---

## Backup & Restore

The **Executive Dashboard** (Super Admin) includes a built-in Backup & Restore system:

- **Create Restore Point**: Saves a full copy of the production database with a timestamp and the creating user's name
- **Restore**: Overwrites the live database with any saved backup
- Backup files are stored in the `data/` directory alongside the live database

> ⚠️ Plan storage accordingly — each backup is a full copy of the `.db` file.

---

## Deployment Guide

For full server deployment instructions (Windows Task Scheduler auto-start, Linux systemd service, SMTP configuration), see **[deployment.md](./deployment.md)**.

---

*PCL Parts Reservation Tracker — Internal Use Only*
