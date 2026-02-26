# Porsche Parts Tracker - User Roles & Permissions Guide

This document outlines the different user types (roles) available in the Porsche Parts Reservation Tracker application, explaining exactly what each role can see and do within the system.

## Summary of All Roles

| Role | Access Level | Can Overwrite/Upload Data? | Can Post/Archive Items? | Can Manage Users? |
|---|---|---|---|---|
| **`super_admin`** | **Total Access** + Exec Dashboard | ✅ Yes | ✅ Yes | ✅ Yes |
| **`admin`** | **Total Access** | ✅ Yes | ✅ Yes | ❌ No |
| **`PRTADV`** | All advisors (Except OTC) | ❌ No | ✅ Yes | ❌ No |
| **`A`** | All advisors (Except OTC) | ❌ No | ❌ No | ❌ No |
| **`Read Only`** | All advisors (View Only) | ❌ No | ❌ No | ❌ No |
| **`SaMnagment`** | EMA, EMB, EMC groups only | ❌ No | ❌ No | ❌ No |
| **`OTC`** | OTC parts only | ❌ No | ✅ Yes | ❌ No |
| **`ServiceADV`**| Their own advisor code only | ❌ No | ❌ No | ❌ No |

---

## Detailed Role Breakdown

### Administrative Roles

These roles are meant for the system administrators and parts managers who need to oversee the entire operation and upload source files from Porsche systems.

#### 👑 `super_admin` (Super Administrator)
* **Purpose:** The highest level of system access. Reserved for the IT administrator or top-level Parts Manager.
* **Capabilities:** 
  * Has access to everything the `admin` has.
  * Extraneous access to the **Executive Dashboard**, which displays live metrics, workload distribution charts, and problem items.
  * Exclusive rights to the **User Management** panel to create, edit, or delete user accounts.
  * Exclusive rights to the **Backup & Restore** functions to save or rewind the database.

#### 👔 `admin` (Administrator)
* **Purpose:** Meant for the Parts Department managers who run the daily uploads.
* **Capabilities:**
  * Can view the parts list for **all service advisors**.
  * Full access to the **Uploads** tab to parse On Order, Back Order, and Invoiced (Shipment) Excel files.
  * Can review shipments, mark items as received, and trigger email notifications.
  * Can post (archive) completed items off the active radar.
  * **Cannot** access system backups, user management, or the Executive Dashboard.

---

### General Advisor Roles

These roles are designed for general parts advisors tracking items across the dealership.

#### 🛠️ `PRTADV` (Parts Advisor - Post Access)
* **Purpose:** For senior or general parts advisors who need to track and finalize orders.
* **Capabilities:**
  * Can view and interact with parts for **all** service advisors **except** OTC (Over The Counter).
  * Has permission to **Post/Archive items**, removing them from the active tracking lists once the customer has picked them up.
  * Cannot manage users or upload data sheets.

#### 👀 `A` (General Viewer)
* **Purpose:** A read-only equivalent to `PRTADV`.
* **Capabilities:**
  * Can view all parts across all service advisors **except** OTC.
  * Can view the Ledger and Item history.
  * **Cannot** post or archive parts, and cannot override or upload statuses.

#### 📖 `Read Only` (Global Observer)
* **Purpose:** Designed for upper management or auditing staff who need to see everything but shouldn't interact with the data lifecycle.
* **Capabilities:**
  * Can view the parts tracking list for **all advisors, including OTC**.
  * Strictly a viewing role; no posting or editing capabilities.

---

### Group & Restricted Roles

These roles restrict the parts catalog to specific dealership groups or individuals.

#### 🏢 `SaMnagment` (Service Management)
* **Purpose:** Tailored for Service Managers who oversee specific groups of advisors.
* **Capabilities:**
  * Inherits a strictly **read-only** view.
  * Filters the parts table so they can **only** see active orders belonging to the `EMA`, `EMB`, and `EMC` service advisor groups.

#### 🛒 `OTC` (Over The Counter)
* **Purpose:** Dedicated purely to OTC parts tracking.
* **Capabilities:**
  * Restricted entirely to viewing items assigned to the **OTC** service advisor group.
  * Despite the restricted view, they **are authorized** to Post/Archive their own OTC items once handed to a customer.

#### 👨‍🔧 `ServiceADV` (Individual Service Advisor)
* **Purpose:** Designed for individual technicians or custom service advisors who only need to track what affects their own bay.
* **Capabilities:**
  * When setting up this user, the admin assigns them a specific "Service Advisor Code" (e.g., `EMA GilbetZ`, `B&P`, etc.).
  * This user logs in and can **only** see parts that are strictly labeled with their assigned code.
  * They have zero posting or archiving powers; it is purely a monitoring and notification tool.

---

## Important Note on Multiple Roles
The system accommodates combination roles! If an employee needs the view restriction of `ServiceADV` but also needs the ability to post items, an admin can theoretically grant them multiple comma-separated roles in the backend. By default, though, sticking to the standard tiered templates above is recommended for clarity.
