import sqlite3
import pandas as pd
import bcrypt
import os
from datetime import datetime
import re
import utils # Added import
from pathlib import Path

import config

def get_connection():
    return sqlite3.connect(config.DB_PATH)

def init_db():
    """
    Initialize the database with the new schema for Type A/B/B1 users
    and the 16-column parts table.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # --- Users Table ---
    # user_type: 'A', 'B', 'B1', 'admin'
    # service_advisor_code: 'EMA', 'EMB', 'EMC', 'B&P', 'OTC' (Only for Type B typically)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL,
            user_type TEXT NOT NULL, 
            service_advisor_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Parts Table ---
    # 16 Columns + Internal flags + Reminder Tracking
    # MUST be created BEFORE the migration checks below
    c.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_no TEXT,               -- 1. Item No.
            item_description TEXT,      -- 2. Item Description
            customer_no TEXT,           -- 3. Customer No.
            customer_name TEXT,         -- 4. Customer Name
            vin TEXT,                   -- 5. VIN
            document_no TEXT,           -- 6. Document No. (Reserved For)
            service_advisor TEXT,       -- 7. Service Advisor
            order_no TEXT,              -- 8. Order No.
            item_status TEXT,           -- 9. Item Status
            remarks TEXT,               -- 10. Remarks
            eta TEXT,                   -- 11. ETA
            updates_log TEXT DEFAULT '',-- 12. Updates (JSON/Newlines)
            ordered_qty INTEGER DEFAULT 0,    -- 13. Ordered QTY
            in_transit_qty INTEGER DEFAULT 0, -- 14. In Transit QTY
            received_qty INTEGER DEFAULT 0,   -- 15. Received QTY
            cardown TEXT,               -- 16. Car Down (Yes/No)
            
            is_archived BOOLEAN DEFAULT 0, -- For Type B1 "Post" action
            source_file_type TEXT,      -- 'OnOrder', 'BackOrder', 'Invoiced'
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            posted_by TEXT,             -- User who archived it
            posted_at TIMESTAMP,        -- Time of archiving
            shipment_ref TEXT,          -- Filename for In Transit batches
            next_info TEXT,             -- From Back Order report
            last_reminder_sent TIMESTAMP, -- Time of last stale stock warning
            custom_stock_date TIMESTAMP,  -- Manual stock date override
            back_order_original_date TIMESTAMP -- Manual back order date override
        )
    ''')

    # SCHEMA MIGRATION: Ensure 'email' exists in users
    try:
        c.execute("SELECT email FROM users LIMIT 1")
    except Exception:
        print("Migrating schema: Adding email to users")
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # SCHEMA MIGRATION: Ensure 'last_reminder_sent' exists in parts
    try:
        c.execute("SELECT last_reminder_sent FROM parts LIMIT 1")
    except Exception:
        print("Migrating schema: Adding last_reminder_sent to parts")
        c.execute("ALTER TABLE parts ADD COLUMN last_reminder_sent TIMESTAMP")

    # SCHEMA MIGRATION: Ensure 'custom_stock_date' exists in parts
    try:
        c.execute("SELECT custom_stock_date FROM parts LIMIT 1")
    except Exception:
        print("Migrating schema: Adding custom_stock_date to parts")
        c.execute("ALTER TABLE parts ADD COLUMN custom_stock_date TIMESTAMP")
        
    # SCHEMA MIGRATION: Ensure 'back_order_original_date' exists in parts
    try:
        c.execute("SELECT back_order_original_date FROM parts LIMIT 1")
    except Exception:
        print("Migrating schema: Adding back_order_original_date to parts")
        c.execute("ALTER TABLE parts ADD COLUMN back_order_original_date TIMESTAMP")
    
    # Check for default admin
    c.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not c.fetchone():
        password_bytes = "admin".encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        c.execute('''
            INSERT INTO users (username, password_hash, user_type, service_advisor_code) 
            VALUES (?, ?, ?, ?)
        ''', ('admin', hashed, 'admin,super_admin', 'ALL')) # Configured as super_admin by default if new
        print("Default admin created.")
        
    # --- Notifications Table ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,           -- Target specific user (optional)
            advisor_code TEXT,         -- Target all users with this code (optional)
            user_type TEXT,            -- Target all users of this type (optional)
            message TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # --- Remarks Table (New) ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS item_remarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER,
            remark_text TEXT,
            follow_up_date DATE,
            remember_on_date DATE,
            entered_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP,  -- New column for Read Receipts
            FOREIGN KEY(part_id) REFERENCES parts(id)
        )
    ''')
    
    # --- Backups Table (New) ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS database_backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT UNIQUE,
            created_by TEXT
        )
    ''')
    
    # Create 'sadmin' user (Super Admin)
    c.execute('SELECT * FROM users WHERE username = ?', ('sadmin',))
    if not c.fetchone():
        password_bytes = "sadmin".encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        # super_admin has ALL roles: admin, super_admin, SADV (to view all), etc. if needed
        # But crucially: 'super_admin' in type.
        c.execute('''
            INSERT INTO users (username, password_hash, user_type, service_advisor_code) 
            VALUES (?, ?, ?, ?)
        ''', ('sadmin', hashed, 'super_admin,admin', 'ALL'))
        print("Super Admin 'sadmin' created.")
        
        
    # SCHEMA MIGRATION: Ensure 'read_at' exists
    try:
        c.execute("SELECT read_at FROM item_remarks LIMIT 1")
    except Exception:
        print("Migrating schema: Adding read_at to item_remarks")
        c.execute("ALTER TABLE item_remarks ADD COLUMN read_at TIMESTAMP")
    
    # MIGRATION: Check if we have legacy remarks to migrate
    # If item_remarks is empty, try to populate from parts.remarks
    c.execute("SELECT COUNT(*) FROM item_remarks")
    if c.fetchone()[0] == 0:
        c.execute("SELECT id, remarks FROM parts WHERE remarks IS NOT NULL AND remarks != ''")
        legacy_rows = c.fetchall()
        if legacy_rows:
            print(f"Migrating {len(legacy_rows)} legacy remarks...")
            migrated_count = 0
            for row in legacy_rows:
                p_id, txt = row
                # Insert details
                c.execute('''
                    INSERT INTO item_remarks (part_id, remark_text, entered_by)
                    VALUES (?, ?, ?)
                ''', (p_id, txt, 'System Migration'))
                migrated_count += 1
            print(f"Migrated {migrated_count} remarks.")
        
        
    # SCHEMA MIGRATION: Ensure 'next_info' exists
    try:
        c.execute("SELECT next_info FROM parts LIMIT 1")
    except Exception:
        print("Migrating schema: Adding next_info to parts")
        c.execute("ALTER TABLE parts ADD COLUMN next_info TEXT")
        
    # DATA MIGRATION: Rename Advisor Codes & Roles
    # 1. Update Advisor Codes in Parts
    updates = {
        "EMA": "EMA GilbetZ",
        "EMB": "EMB TonyR",
        "EMC": "EMC JackS"
    }
    for old, new in updates.items():
        c.execute("UPDATE parts SET service_advisor = ? WHERE service_advisor = ?", (new, old))
        c.execute("UPDATE users SET service_advisor_code = ? WHERE service_advisor_code = ?", (new, old))
        
    # 2. Update User Roles - Migration SADV -> PRTADV
    try:
        # Check if we have 'SADV' users to migrate
        c.execute("SELECT count(*) FROM users WHERE user_type LIKE '%SADV%'")
        if c.fetchone()[0] > 0:
            print("Migrating schema: Renaming SADV user role to PRTADV")
            c.execute("UPDATE users SET user_type = replace(user_type, 'SADV', 'PRTADV') WHERE user_type LIKE '%SADV%'")
            # Also update B1 legacy just in case
            c.execute("UPDATE users SET user_type = replace(user_type, 'B1', 'PRTADV') WHERE user_type LIKE '%B1%'")
    except Exception as e:
        print(f"Migration error (SADV->PRTADV): {e}")

    conn.commit()
    conn.close()

# --- User Management ---

def create_user(username, password, user_type, service_advisor_code, email=None):
    conn = get_connection()
    c = conn.cursor()
    
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # ensure user_type is string if list provided
    if isinstance(user_type, list):
        user_type = ",".join(user_type)
    
    try:
        c.execute('''
            INSERT INTO users (username, password_hash, user_type, service_advisor_code, email)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, hashed, user_type, service_advisor_code, email))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False
    except Exception as e:
        print(f"Error creating user: {e}")
        conn.close()
        return False
        
    conn.close()
    return True

def verify_user(username, password):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    
    if user:
        stored_hash = user['password_hash']
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return dict(user)
    return None

def get_all_users():
    conn = get_connection()
    df = pd.read_sql('SELECT username, user_type, service_advisor_code, created_at FROM users', conn)
    conn.close()
    return df

def delete_user_by_username(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()

def get_user_emails_by_advisor_code(advisor_code):
    """
    Fetches ALL emails for a specific advisor code. 
    Returns a list of tuples: (email, username).
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT email, username FROM users WHERE service_advisor_code = ? AND email IS NOT NULL AND email != ""', (advisor_code,))
    rows = c.fetchall()
    conn.close()
    return rows # [(email, username), ...]

# --- Data Management ---

def insert_part_record(data, source_type):
    """
    Insert a single record. 
    In specific parsers, we might want to check for duplicates or update existing 
    based on Order No + Item No.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Logic to upsert could go here. For now, simple insert to get it working.
    # We might need a composite key check: OrderNo + ItemNo
    
    # BackOrder Logic (UPSERT)
    # 1. Check if item exists (Same Item No + Same Order No)
    #    If so, UPDATE status -> 'Back Order' and update ETA/Cardown/Qty
    # 2. If not, INSERT regular (with Customer Linking)
    
    # UPSERT / SYNC Logic with Smart Matching
    if source_type in ['BackOrder', 'Invoiced']:
        item_val = data.get('item_no')
        input_order_norm = utils.smart_normalize_order(data.get('order_no'))
        
        # 1. Fetch potential candidates by Item No (Robust: Exact OR LTRIM logic for leading zeros)
        # We need columns: id, order_no, customer info (for linking)

        # UPDATED: Fetching more columns for full email notification, AND updates_log for aging calculation
        c.execute('''
            SELECT id, order_no, item_status, customer_name, customer_no, service_advisor, ordered_qty, item_no, document_no, eta, cardown, item_description, updates_log
            FROM parts 
            WHERE item_no = ? OR ltrim(item_no, '0') = ltrim(?, '0')
        ''', (item_val, item_val))
        
        candidates = c.fetchall()
        matches = []
        
        for cand in candidates:
            # Unpack attributes from db
            c_id, c_order, c_status, c_cust, c_cust_no, c_adv, c_qty, c_item_no, c_doc, c_eta, c_cardown, c_desc, c_log = cand
            # Smart Normalize DB value
            db_order_norm = utils.smart_normalize_order(c_order)
            
            is_match = False
            
            if source_type == 'Invoiced':
                 # Relax PAG requirement for Invoiced
                 # Match on Customer Name if provided
                 input_cust = (data.get('customer_name') or '').strip().lower()
                 db_cust = (c_cust or '').strip().lower()
                 
                 # 1. Customer Name Match
                 if input_cust and db_cust and input_cust == db_cust:
                     is_match = True
                 # 2. Fallback to PAG Match
                 elif db_order_norm == input_order_norm:
                     is_match = True
            
            else:
                # BackOrder: 
                # 1. Strict Match
                if db_order_norm and input_order_norm and db_order_norm == input_order_norm:
                    is_match = True
                
                # 2. Loose Numeric Match (Extract digits and compare)
                # "26PAG52" vs "52" or "04 52"
                elif db_order_norm and input_order_norm:
                    # Extract ALL digits from both strings
                    db_nums_list = re.findall(r'\d+', db_order_norm)
                    in_nums_list = re.findall(r'\d+', input_order_norm)
                    
                    if db_nums_list and in_nums_list:
                        # Compare the LAST found number block (stripped of zeros)
                        # e.g. "26PAG052" -> ["26", "052"] -> last is "052" -> "52"
                        # "04 52" -> ["04", "52"] -> last is "52"
                        db_last = db_nums_list[-1].lstrip('0')
                        in_last = in_nums_list[-1].lstrip('0')
                         
                        if db_last == in_last and db_last != '':
                            is_match = True
                        
                # 3. Fallback: exact customer name match
                elif (data.get('customer_name') and c_cust and 
                      data.get('customer_name').strip().lower() == c_cust.strip().lower()):
                      is_match = True
            
            if is_match:
                matches.append(cand)
        
        if matches:
            # We found matching records!
            ids_to_update = [m[0] for m in matches]
            placeholders = ','.join('?' for _ in ids_to_update)
            
            if source_type == 'BackOrder':
                # Action: Update Status to BackOrder, Sync Info
                # Use custom back order date if provided, otherwise use current date
                bo_date = data.get('back_order_date', datetime.now().strftime('%Y-%m-%d'))
                log_update = f"\n[{bo_date} 00:00] System: Back Order Update (Smart Match)"
                
                # Update SQL
                c.execute(f'''
                    UPDATE parts
                    SET item_status = 'Back Order',
                        eta = ?,
                        next_info = ?,
                        cardown = ?,
                        updates_log = updates_log || ?,
                        last_updated = CURRENT_TIMESTAMP,
                        source_file_type = 'BackOrder'
                    WHERE id IN ({placeholders})
                ''', [data.get('eta'), data.get('next_info', ''), data.get('cardown'), log_update] + ids_to_update)
                
                conn.commit()
                conn.close()
                
                # Notifications Buffer
                notifs = []
                for m in matches:
                     # Unpack again match tuple
                     c_id, c_order, c_status, c_cust, c_cust_no, c_adv, c_qty, c_item_no, c_doc, c_eta, c_cardown, c_desc, c_log = m
                     
                     # Calculate Duration using EXISTING log + update we just did logic-wise?
                     # Actually fetching fresh log is expensive. Let's use existing log to approximate or say "Updated Just Now".
                     # User wants "Duration". 
                     # If status was already BackOrder, we use utils.get_aging_text with existing log.
                     # If status was NOT Back Order, it just became one, so duration is 0 days.
                     
                     duration_str = ""
                     if c_status == 'Back Order':
                         duration_str = utils.get_aging_text(c_log, 'Back Order')
                     else:
                         duration_str = "B.O. 0 days"
                     
                     notifs.append({
                         'advisor': c_adv, 
                         'item_no': c_item_no, 
                         'status': 'Back Order',
                         'description': c_desc,
                         'document_no': c_doc,
                         'customer_name': c_cust,
                         'customer_no': c_cust_no,
                         'order_no': c_order,
                         'ordered_qty': c_qty,
                         'eta': data.get('eta'), 
                         'cardown': data.get('cardown'),
                         'duration': duration_str
                     })
                return notifs

            elif source_type == 'Invoiced':
                # ...
                
                log_update = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] System: In Transit (Shipment: {data.get('shipment_ref')})"
                
                ids_in_transit = []
                ids_reordered = []
                notifs = []
                
                for m in matches:
                    c_id, c_order, c_status, c_cust, c_cust_no, c_adv, c_qty, c_item_no, c_doc, c_eta, c_cardown, c_desc, c_log = m
                    
                    new_status = 'In Transit'
                    if c_status == 'Partially Received':
                        ids_reordered.append(c_id)
                        new_status = 'Reordered'
                    else:
                        ids_in_transit.append(c_id)
                        
                    notifs.append({
                         'advisor': c_adv, 
                         'item_no': c_item_no, 
                         'status': new_status,
                         'description': c_desc,
                         'document_no': c_doc,
                         'customer_name': c_cust,
                         'customer_no': c_cust_no,
                         'order_no': c_order,
                         'ordered_qty': c_qty,
                         'eta': data.get('eta'), # New Info
                         'in_transit_qty': data.get('in_transit_qty'), # New Info
                         'duration': '' # In Transit usually doesn't show aging days until received
                     })
                
                # ... (SQL Updates omitted for brevity, they are unchanged)
                if ids_reordered:
                     ph_re = ','.join('?' for _ in ids_reordered)
                     log_re = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] System: Reordered (Shipment: {data.get('shipment_ref')})"
                     c.execute(f'''UPDATE parts SET item_status = 'Reordered', shipment_ref = ?, eta = ?, updates_log = updates_log || ?, last_updated = CURRENT_TIMESTAMP, source_file_type = 'Invoiced' WHERE id IN ({ph_re})''', [data.get('shipment_ref'), data.get('eta'), log_re] + ids_reordered)

                if ids_in_transit:
                     ph_it = ','.join('?' for _ in ids_in_transit)
                     c.execute(f'''UPDATE parts SET item_status = 'In Transit', in_transit_qty = ?, shipment_ref = ?, eta = ?, updates_log = updates_log || ?, last_updated = CURRENT_TIMESTAMP, source_file_type = 'Invoiced' WHERE id IN ({ph_it})''', [data.get('received_qty'), data.get('shipment_ref'), data.get('eta'), log_update] + ids_in_transit)
                    
                conn.commit()
                conn.close()
                return notifs
        
    # Regular Insert (OnOrder)
    if source_type != 'OnOrder':
        conn.close()
        return []
    
    # Insert SQL
    log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] System: Uploaded (Source: OnOrder)"
    
    try:
        c.execute('''
            INSERT INTO parts (
                item_no, item_description, customer_no, customer_name, 
                document_no, order_no, service_advisor, ordered_qty, 
                item_status, eta, updates_log, source_file_type, cardown, is_archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            data.get('item_no'), 
            data.get('item_description'),
            data.get('customer_no'),
            data.get('customer_name'),
            data.get('document_no'),
            data.get('order_no'),
            data.get('service_advisor'),
            data.get('ordered_qty'),
            'On Order',
            data.get('eta'),
            log_entry,
            'OnOrder',
            data.get('cardown', 'No')
        ))
    except Exception as e:
        print(f"Error inserting OnOrder part: {e}")

    
    conn.commit()
    conn.close()
    
    # Return Notification for Insert (Use FULL data)
    # Return copy of data but ensure status is set
    notif_data = data.copy()
    notif_data['status'] = 'On Order'
    # Rename advisor key to match others if needed, though 'service_advisor' is in data
    notif_data['advisor'] = data.get('service_advisor')
    
    return [notif_data]

def get_parts_view(user_type, service_advisor_code=None):
    conn = get_connection()
    
    # Base Query with Subqueries for Remarks
    base_query = '''
        SELECT p.*, 
        (SELECT remark_text FROM item_remarks r WHERE r.part_id = p.id ORDER BY r.created_at DESC LIMIT 1) as latest_remark,
        (SELECT read_at FROM item_remarks r WHERE r.part_id = p.id ORDER BY r.created_at DESC LIMIT 1) as latest_remark_read_at
        FROM parts p 
        WHERE p.is_archived = 0
        -- Show Back Order ONLY if it has a customer (Linked)
        AND (
            p.item_status != 'Back Order' 
            OR (p.item_status = 'Back Order' AND p.customer_name IS NOT NULL AND p.customer_name != '')
        )
    '''
    
    params = []
    
    # Role Logic
    # View All Types
    # Role Logic
    # 1. Admin or AA: View Everything
    if user_type in ['admin', 'AA']:
        pass
        
    # 2. General View (A, PRTADV): View All EXCEPT OTC
    elif user_type in ['A', 'PRTADV', 'SADV']: # SADV for safety
        base_query += " AND p.service_advisor != 'OTC'"
        
    # Group View: EMB Role
    elif user_type == 'EMB':
        base_query += " AND p.service_advisor IN ('EMA GilbetZ', 'EMB TonyR', 'EMC JackS')"
        
    # Restricted View: OTC
    elif user_type == 'OTC':
        base_query += " AND p.service_advisor = 'OTC'"
        
    # Restricted View: Type B (or fallback)
    else:
        # Default fallback for B or others is Own Code Only
        base_query += " AND p.service_advisor = ?"
        params.append(service_advisor_code)
    
    # Sort
    base_query += " ORDER BY p.last_updated DESC"
        
    try:
        df = pd.read_sql(base_query, conn, params=params)
    except Exception as e:
        print(f"Error fetching parts view: {e}")
        df = pd.DataFrame()
        
    conn.close()
    return df

def get_archived_parts():
    """
    Fetches all parts where is_archived = 1 (Posted items).
    """
    conn = get_connection()
    c = conn.cursor()
    # Also fetch the updates_log to see when it was posted?
    query = '''
        SELECT * FROM parts 
        WHERE is_archived = 1 
        ORDER BY last_updated DESC
    '''
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def restore_archived_part(part_id, user_name):
    """
    Restores an archived part (Unship).
    """
    conn = get_connection()
    c = conn.cursor()
    log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {user_name}: Restored (Unshipped)"
    try:
        c.execute('''
            UPDATE parts 
            SET is_archived = 0, updates_log = updates_log || ? 
            WHERE id = ?
        ''', (log_entry, part_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error restoring part: {e}")
        return False
    finally:
        conn.close()


def archive_part(part_id, user_name):
    """
    Archives a part (Type B1 Post action).
    """
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"\n[{now_str}] {user_name}: Archived (Posted)"
    try:
        c.execute('''
            UPDATE parts 
            SET is_archived = 1, 
                updates_log = updates_log || ?,
                posted_by = ?,
                posted_at = ?
            WHERE id = ?
        ''', (log_entry, user_name, now_str, part_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error archiving: {e}")
        return False
    finally:
        conn.close()

def update_remarks(part_id, new_remarks, user_name):
    # Backward compatibility wrapper, or maybe decommission?
    # For now, if "remarks" column is edited directly (legacy), we add a new entry?
    # Or strict deprecation? 
    # Let's map this to add_remark for safety if called.
    add_remark(part_id, new_remarks, None, None, user_name)

def add_remark(part_id, text, follow_up, remember_on, user_name):
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Insert Remark
    c.execute('''
        INSERT INTO item_remarks (part_id, remark_text, follow_up_date, remember_on_date, entered_by)
        VALUES (?, ?, ?, ?, ?)
    ''', (part_id, text, follow_up, remember_on, user_name))
    
    # 2. Update parent part log
    log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {user_name}: New Remark Added"
    c.execute("UPDATE parts SET updates_log = updates_log || ? WHERE id = ?", (log_entry, part_id))
    
    # 3. Trigger Notification (Admin -> Advisor)
    if 'admin' in user_name.lower(): # Simple check, better if we passed roles
        # Get part advisor
        c.execute("SELECT service_advisor, item_no FROM parts WHERE id = ?", (part_id,))
        row = c.fetchone()
        if row:
            advisor, item_no = row
            if advisor and advisor != 'Unknown':
                 add_notification_internal(c, f"Admin added remark on Item {item_no}.", target_advisor_code=advisor)
    
    conn.commit()
    conn.close()

def get_remarks_for_part(part_id):
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM item_remarks WHERE part_id = ? ORDER BY created_at DESC", conn, params=(part_id,))
    conn.close()
    return df

def check_daily_reminders(username):
    """
    Checks if there are any 'remember_on_date' OR 'follow_up_date' = TODAY for this user.
    """
    conn = get_connection()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Assumption: If I entered the remark, I want to be reminded.
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, p.item_no, r.remark_text, r.follow_up_date, r.remember_on_date
        FROM item_remarks r
        JOIN parts p ON r.part_id = p.id
        WHERE (r.remember_on_date = ? OR r.follow_up_date = ?) AND r.entered_by = ?
    ''', (today, today, username))
    
    alerts = []
    for row in cursor.fetchall():
        r_id, item_no, text, f_date, r_date = row
        
        # Determine strict type for the message label
        # Ideally if both match, we can say "Reminder & Follow Up"
        is_rem = str(r_date) == today
        is_fup = str(f_date) == today
        
        label = "Reminder"
        if is_rem and is_fup:
            label = "Reminder & Follow Up"
        elif is_fup:
            label = "Follow Up"
            
        alerts.append(f"{label} (Item {item_no}): {text}")
    
    conn.close()
    return alerts

# Helper for internal notification use
def add_notification_internal(cursor, message, target_user_id=None, target_advisor_code=None, target_type=None):
    cursor.execute('''
        INSERT INTO notifications (user_id, advisor_code, user_type, message)
        VALUES (?, ?, ?, ?)
    ''', (target_user_id, target_advisor_code, target_type, message))

# --- Notifications ---

def add_notification(message, target_user_id=None, target_advisor_code=None, target_type=None):
    """
    Adds a notification. 
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO notifications (user_id, advisor_code, user_type, message)
        VALUES (?, ?, ?, ?)
    ''', (target_user_id, target_advisor_code, target_type, message))
    conn.commit()
    conn.close()

def get_notifications_for_user(user_id, user_type_str, advisor_code):
    """
    Get generic notifications or specific ones for this user.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Filter Logic
    # 1. Admin: View All
    if user_type_str and 'admin' in str(user_type_str):
        c.execute("SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT 50")
    else:
        # 2. Others: View Global + Specific to Code/Type
        query = '''
            SELECT * FROM notifications 
            WHERE is_read = 0 
            AND (
                -- a. Global (No target)
                ( (advisor_code IS NULL OR advisor_code = '') AND (user_type IS NULL OR user_type = '') )
                OR
                -- b. Targeted to my Advisor Code (or ALL)
                (advisor_code = ? OR advisor_code = 'ALL')
                OR
                -- c. Targeted to my User Type (e.g. 'B' targeting 'B')
                -- Check if Notification's user_type is present in my user_type_str list
                (user_type IS NOT NULL AND user_type != '' AND ? LIKE '%' || user_type || '%')
            )
            ORDER BY created_at DESC LIMIT 50
        '''
        # Ensure advisor_code is string or None
        c.execute(query, (advisor_code, user_type_str))
    
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_notification_read(notif_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()

def mark_all_notifications_read():
    """
    Marks all currently unread notifications as read.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0")
    conn.commit()
    conn.close()
def clear_all_data():
    """
    Clears all business data (Parts, Remarks, Notifications) but KEEPS Users.
    For Testing Purposes Only.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM parts")
        c.execute("DELETE FROM item_remarks")
        c.execute("DELETE FROM notifications")
        # Reset sequences if desired, but not strictly necessary
        c.execute("UPDATE sqlite_sequence SET seq=0 WHERE name IN ('parts', 'item_remarks', 'notifications')")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clearing data: {e}")
        return False
    finally:
        conn.close()

# --- Shipment Management ---

def get_pending_shipments():
    """
    Returns a list of unique shipment references that have items 'In Transit'.
    """
    conn = get_connection()
    c = conn.cursor()
    # Distinct shipment items that are In Transit
    c.execute('''
        SELECT DISTINCT shipment_ref 
        FROM parts 
        WHERE (item_status = 'In Transit' OR item_status = 'Reordered')
          AND shipment_ref IS NOT NULL 
          AND shipment_ref != ''
    ''')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_shipment_items(shipment_ref):
    """
    Returns all items belonging to a specific shipment reference that are In Transit.
    """
    conn = get_connection()
    # We want these columns for display
    query = '''
        SELECT * 
        FROM parts 
        WHERE shipment_ref = ? 
          AND (item_status = 'In Transit' OR item_status = 'Reordered')
    '''
    df = pd.read_sql(query, conn, params=(shipment_ref,))
    conn.close()
    conn.close()
    return df

def get_all_shipments_summary():
    """
    Returns summary of all shipments (Invoiced uploads).
    """
    conn = get_connection()
    # Logic: Group by shipment_ref
    # Status is 'In Transit' if ANY item is In Transit (or Reordered).
    # Status is 'Received' if ALL items are Received (or Archived/Posted).
    query = '''
        SELECT 
            shipment_ref,
            MIN(eta) as current_eta,
            MAX(last_updated) as last_update,
            COUNT(*) as total_items,
            SUM(CASE WHEN item_status IN ('In Transit', 'Reordered') THEN 1 ELSE 0 END) as in_transit_count,
            SUM(CASE WHEN item_status = 'Received' THEN 1 ELSE 0 END) as received_count
        FROM parts
        WHERE shipment_ref IS NOT NULL AND shipment_ref != ''
        GROUP BY shipment_ref
        ORDER BY last_update DESC
    '''
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Post-process to determine display status
    def get_status(row):
        if row['in_transit_count'] > 0:
            return 'In Transit'
        return 'Received'
        
    if not df.empty:
        df['status'] = df.apply(get_status, axis=1)
        
    return df

def update_shipment_eta(shipment_ref, new_eta, user_name):
    """
    Updates ETA for all items in a shipment (only active ones).
    Returns list of affected items for notification.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Fetch affected items for notification
    c.execute('''
        SELECT item_no, item_description, service_advisor, customer_name, order_no, document_no, item_status
        FROM parts 
        WHERE shipment_ref = ? AND item_status IN ('In Transit', 'Reordered')
    ''', (shipment_ref,))
    
    rows = c.fetchall()
    affected_items = []
    columns = ['item_no', 'description', 'advisor', 'customer_name', 'order_no', 'document_no', 'status']
    for row in rows:
        item = dict(zip(columns, row))
        item['new_eta'] = new_eta
        affected_items.append(item)
        
    log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {user_name}: ETA Updated to {new_eta}"
    
    try:
        c.execute('''
            UPDATE parts 
            SET eta = ?, updates_log = updates_log || ?, last_updated = CURRENT_TIMESTAMP
            WHERE shipment_ref = ? AND item_status IN ('In Transit', 'Reordered')
        ''', (new_eta, log_entry, shipment_ref))
        conn.commit()
        return affected_items
    except Exception as e:
        print(f"Error updating ETA: {e}")
        return []
    finally:
        conn.close()



def receive_shipment_items(records, user_name):
    """
    Receives items from Review stage.
    records: list of dicts with {'id': int, 'received_qty': int}
    """
    conn = get_connection()
    c = conn.cursor()
    count = 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Store IDs for notification
    received_ids = []
    notifs = []
    
    try:
        for rec in records:
            p_id = rec['id']
            qty = rec['received_qty']
            
            # Fetch current state
            c.execute("SELECT ordered_qty, received_qty, service_advisor, item_no, item_description, document_no, customer_no, customer_name FROM parts WHERE id = ?", (p_id,))
            row = c.fetchone()
            
            ordered = row[0] if row else 0
            current_received = row[1] if row and row[1] else 0
            advisor = row[2] if row else 'Unknown'
            item_no = row[3] if row else 'Unknown'
            desc = row[4] if row else ''
            
            doc_no = row[5] if row else ''
            cust_no = row[6] if row else ''
            cust_name = row[7] if row else ''
            
            # Accumulate
            new_total_received = current_received + qty
            
            # Determine Status
            if new_total_received >= ordered:
                new_status = 'Received'
            else:
                new_status = 'Partially Received'
                
            log_entry = f"\n[{now_str}] {user_name}: Received +{qty} (Total: {new_total_received} / {ordered})"
            
            # Update
            c.execute('''
                UPDATE parts 
                SET received_qty = ?, 
                    item_status = ?,
                    updates_log = updates_log || ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_total_received, new_status, log_entry, p_id))
            
            count += 1
            # Add to Notification List
            notifs.append({
                'advisor': advisor,
                'item_no': item_no,
                'status': new_status,
                'description': desc,
                'document_no': doc_no,
                'customer_no': cust_no,
                'customer_name': cust_name
            })
        
        conn.commit()
    except Exception as e:
        print(f"Error receiving items: {e}")
    finally:
        conn.close()
        
    return count, notifs

# --- Email Notification Logic ---
import mailer

def notify_part_arrival(item_id):
    """
    Triggers immediate email to advisor when part is FULLY received.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT item_no, item_description, service_advisor, customer_name, order_no FROM parts WHERE id = ?", (item_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        item_no, desc, advisor, cust, order = row
        if not advisor or advisor == 'Unknown':
            return
            
        email = mailer.get_advisor_email(advisor)
        subject = f"PART ARRIVAL: {item_no} for {cust}"
        
        body = f"""
        <h3>Part Arrival Confirmation</h3>
        <p>A part assigned to you has arrived and is ready for pickup.</p>
        <ul>
            <li><b>Part Number:</b> {item_no}</li>
            <li><b>Description:</b> {desc}</li>
            <li><b>Customer:</b> {cust}</li>
            <li><b>Order No:</b> {order}</li>
            <li><b>Service Advisor:</b> {advisor}</li>
        </ul>
        <p>Please collect it from the warehouse.</p>
        """
        mailer.send_email(email, subject, body)

def generate_daily_advisor_brief():
    """
    Generates summary email for each advisor:
    1. Newly Arrived (Last 24h)
    2. Critical Aging (> 7 Days)
    3. Pending ETA (Today)
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Get all active parts
    query = "SELECT * FROM parts WHERE is_archived = 0" 
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        return
    
    advisors = df['service_advisor'].dropna().unique()
    
    for advisor in advisors:
        if not advisor or advisor == 'Unknown':
            continue
            
        # Filter for this advisor
        adv_df = df[df['service_advisor'] == advisor]
        
        # 1. Newly Arrived (Last 24h)
        # We need to detect status change time. 'last_updated' is a proxy.
        now = datetime.now()
        yesterday = now - timedelta(hours=24)
        
        # Convert timestamp strings to datetime objects for comparison
        # last_updated format: YYYY-MM-DD HH:MM:SS (SQLite default)
        try:
            adv_df['last_updated_dt'] = pd.to_datetime(adv_df['last_updated'])
        except:
            continue

        new_arrivals = adv_df[
            (adv_df['item_status'] == 'Received') & 
            (adv_df['last_updated_dt'] >= yesterday)
        ]
        
        # 2. Critical Aging (> 7 Days)
        # Helper to calc days using utils
        def get_days(log):
             return utils.get_days_in_stock(log)
        
        adv_df['aging_days'] = adv_df['updates_log'].apply(get_days)
        critical = adv_df[
            (adv_df['item_status'] == 'Received') & 
            (adv_df['aging_days'] > 7)
        ]
        
        # 3. Pending ETA (Today)
        # ETA is YYYY-MM-DD
        today_str = now.strftime('%Y-%m-%d')
        pending_eta = adv_df[
            (adv_df['item_status'] != 'Received') & 
            (adv_df['eta'] == today_str)
        ]
        
        # Generate HTML
        if new_arrivals.empty and critical.empty and pending_eta.empty:
            continue # Nothing to report
            
        html = f"<h2>Morning Brief for {advisor}</h2>"
        
        if not new_arrivals.empty:
            html += "<h3>Newly Arrived (Last 24h)</h3>"
            html += new_arrivals[['item_no', 'item_description', 'customer_name']].to_html(index=False)
            
        if not critical.empty:
            html += "<h3>Critical Aging (> 7 Days)</h3>"
            html += critical[['item_no', 'customer_name', 'aging_days']].to_html(index=False)

        if not pending_eta.empty:
            html += "<h3>Pending Delivery Today</h3>"
            html += pending_eta[['item_no', 'customer_name', 'item_status']].to_html(index=False)
            
        email = mailer.get_advisor_email(advisor)
        mailer.send_email(email, f"Morning Brief: {advisor}", html)

def remove_items_from_shipment(ids_to_remove, user_name):
    """
    Removes items from specific shipment.
    Logic:
    - If item was created by 'Invoiced' (Source Invoiced) -> DELETE.
    - If item was 'On Order' (Source OnOrder) -> REVERT status.
    """
    conn = get_connection()
    c = conn.cursor()
    count_del = 0
    count_revert = 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    try:
        if not ids_to_remove:
            return 0, 0

        # Fetch details to decide action
        placeholders = ','.join('?' for _ in ids_to_remove)
        c.execute(f"SELECT id, source_file_type, received_qty, updates_log FROM parts WHERE id IN ({placeholders})", ids_to_remove)
        rows = c.fetchall()
        
        for row in rows:
            p_id = row[0]
            src = row[1] 
            log_text = row[3] or ""
            
            # Check for "Source: OnOrder" to determine if it's an existing item
            is_existing_item = "Source: OnOrder" in log_text or "Source: BackOrder" in log_text
            
            if not is_existing_item:
                # Created by this invoice -> DELETE
                c.execute("DELETE FROM parts WHERE id = ?", (p_id,))
                count_del += 1
            else:
                # Existing item -> REVERT
                curr_recv = row[2] or 0
                new_status = 'Partially Received' if curr_recv > 0 else 'On Order'
                
                log_entry = f"\n[{now_str}] {user_name}: Removed from Shipment (Reverted to {new_status})"
                
                c.execute('''
                    UPDATE parts 
                    SET item_status = ?,
                        shipment_ref = NULL,
                        in_transit_qty = 0,
                        updates_log = updates_log || ?,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_status, log_entry, p_id))
                count_revert += 1
        
        conn.commit()
    except Exception as e:
        print(f"Error removing items: {e}")
    finally:
        conn.close()
        
    return count_del, count_revert

def archive_by_document_no(document_no, user_name):
    """
    Archives all active parts associated with a specific Document No.
    Returns the count of archived items.
    """
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    count = 0
    
    try:
        # Find active items with this document_no
        c.execute("SELECT count(*) FROM parts WHERE document_no = ? AND is_archived = 0", (document_no,))
        count = c.fetchone()[0]
        
        if count > 0:
            log_entry = f"\n[{now_str}] {user_name}: Bulk Posted (Document: {document_no})"
            c.execute('''
                UPDATE parts 
                SET is_archived = 1,
                    item_status = 'Posted',
                    posted_at = ?,
                    updates_log = updates_log || ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE document_no = ? AND is_archived = 0
            ''', (now_str, log_entry, document_no))
            conn.commit()
            
    except Exception as e:
        print(f"Error bulk posting: {e}")
        count = 0 
    finally:
        conn.close()
        
    return count

# --- Ledger / History ---

def get_item_details(item_no_query, user_type='admin', service_advisor_code=None):
    """
    Search for parts by Item No (partial match), filtered by user permissions.
    Returns basic info + updates_log.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Base Query
    query = '''
        SELECT * FROM parts 
        WHERE (item_no LIKE ? OR order_no LIKE ? OR customer_name LIKE ?)
    '''
    params = [f"%{item_no_query}%", f"%{item_no_query}%", f"%{item_no_query}%"]
    
    # Role Logic (Mirroring get_parts_view)
    # user_type might be "admin,super_admin" or just "PRTADV"
    # Ensure we split and check safely
    if not user_type: user_type = ''
    roles = [r.strip() for r in user_type.split(',')]
    
    if 'admin' in roles or 'super_admin' in roles or 'AA' in roles:
        pass # View All
    elif 'A' in roles or 'PRTADV' in roles or 'SADV' in roles:
        query += " AND service_advisor != 'OTC'"
    elif 'EMB' in roles:
        query += " AND service_advisor IN ('EMA GilbetZ', 'EMB TonyR', 'EMC JackS')"
    elif 'OTC' in roles:
        query += " AND service_advisor = 'OTC'"
    else:
        # Default / Type B
        query += " AND service_advisor = ?"
        params.append(service_advisor_code)
        
    query += " ORDER BY id DESC"
    
    c.execute(query, params)
    
    rows = c.fetchall()
    
    # Get columns
    cols = [description[0] for description in c.description]
    df = pd.DataFrame(rows, columns=cols)
    
    conn.close()
    return df

def mark_remarks_as_read(part_id, user_name):
    """
    Marks all remarks for a part as read.
    """
    conn = get_connection()
    c = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        c.execute('''
            UPDATE item_remarks
            SET read_at = ?
            WHERE part_id = ? AND read_at IS NULL
        ''', (now_str, part_id))
        count = c.rowcount
        conn.commit()
    except Exception as e:
        print(f"Error marking read: {e}")
        count = 0
        
    conn.close()
    return count

# --- Dashboard & Metrics ---
def get_dashboard_metrics():
    """
    Returns a dict of high-level metrics for the Super Admin dashboard.
    """
    conn = get_connection()
    c = conn.cursor()
    
    metrics = {}
    
    # 1. Active Orders Count (Not Archived)
    c.execute("SELECT COUNT(*) FROM parts WHERE is_archived = 0")
    metrics['active_orders'] = c.fetchone()[0]
    
    # 2. Car Down Count
    c.execute("SELECT COUNT(*) FROM parts WHERE cardown LIKE 'Yes%' AND is_archived = 0")
    metrics['car_down'] = c.fetchone()[0]
    
    # 3. Received (In Stock) Count
    c.execute("SELECT COUNT(*) FROM parts WHERE item_status = 'Received' AND is_archived = 0")
    metrics['received_count'] = c.fetchone()[0]
    
    conn.close()
    return metrics

def get_stale_stock_candidates(days_threshold=7):
    """
    Returns list of items that are 'Received' and have been so for > days_threshold.
    Calculates duration by parsing updates_log.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT * FROM parts 
        WHERE item_status = 'Received' 
        AND is_archived = 0
    ''')
    rows = c.fetchall()
    conn.close()
    
    stale_items = []
    
    for row in rows:
        # Get duration integer
        log = row['updates_log']
        custom_date = row.get('custom_stock_date') # might wait need to ensure col exists in row (it does via select *)
        aging_text = utils.get_aging_text(log, 'Received', custom_date) # e.g. "IS 5 days"
        
        # Parse int
        days = 0
        if 'IS' in aging_text and 'days' in aging_text:
            try:
                days = int(aging_text.split()[1])
            except:
                days = 0
                
        if days >= days_threshold:
            # Check if warning was sent recently? (Optional, skipping for now to allow manual re-trigger)
            item = dict(row)
            item['days_in_stock'] = days
            stale_items.append(item)
            
    return stale_items

def update_last_reminder(item_ids):
    """
    Updates the last_reminder_sent timestamp for a list of item IDs.
    """
    if not item_ids: return
    conn = get_connection()
    c = conn.cursor()
    placeholders = ','.join('?' for _ in item_ids)
    c.execute(f'''
        UPDATE parts 
        SET last_reminder_sent = CURRENT_TIMESTAMP 
        WHERE id IN ({placeholders})
    ''', item_ids)
    conn.commit()
    conn.close()

# --- Advanced Analytics ---
def get_top_ordered_parts(limit=10):
    """
    Returns data for the Top N most ordered part numbers.
    Aggregate across ALL history (active + archived).
    """
    conn = get_connection()
    # Normalize Item No (remove spaces, uppercase)
    # Simple Group By
    df = pd.read_sql_query('''
        SELECT item_no, item_description, COUNT(*) as frequency, SUM(ordered_qty) as total_qty
        FROM parts
        GROUP BY item_no
        ORDER BY frequency DESC
        LIMIT ?
    ''', conn, params=(limit,))
    conn.close()
    return df

# --- Backup / Restore System ---
import shutil

def create_database_backup(user_name):
    """
    Creates a copy of the current DB file to the backups/ folder 
    and logs it in the database_backups table.
    """
    print(f"DEBUG: Starting backup creation for {user_name}...")
    
    if not config.DB_PATH.exists():
        print(f"DEBUG: DB file not found at {config.DB_PATH}")
        return False, "Database file not found."
        
    backup_dir = config.DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    print(f"DEBUG: Backup directory: {backup_dir}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}_{user_name}.db"
    backup_path = backup_dir / backup_filename
    print(f"DEBUG: Target backup path: {backup_path}")
    
    try:
        # 1. Copy file
        shutil.copy2(config.DB_PATH, backup_path)
        print("DEBUG: File copy successful.")
        
        # 2. Log to DB
        conn = get_connection()
        c = conn.cursor()
        
        # Ensure table exists (just in case)
        c.execute('''CREATE TABLE IF NOT EXISTS database_backups
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT,
                      file_path TEXT,
                      created_by TEXT,
                      timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        c.execute('''
            INSERT INTO database_backups (name, file_path, created_by)
            VALUES (?, ?, ?)
        ''', (backup_filename, str(backup_path), user_name))
        conn.commit()
        conn.close()
        print("DEBUG: DB log insertion successful.")
        
        return True, f"Backup created: {backup_filename}"
    except Exception as e:
        print(f"DEBUG: Backup failed with error: {e}")
        return False, str(e)

def get_available_backups():
    """Returns list of backups from DB table."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM database_backups ORDER BY timestamp DESC LIMIT 20")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def restore_database_backup(backup_id):
    """
    Restores the database from a backup file.
    DANGEROUS: Overwrites current DB.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path FROM database_backups WHERE id = ?", (backup_id,))
    res = c.fetchone()
    conn.close()
    
    if not res:
        return False, "Backup record not found."
        
    backup_path = Path(res[0])
    if not backup_path.exists():
        return False, "Backup file missing from disk."
        
    # Safety: Make a temporary 'pre-restore' backup just in case? 
    # Let's skip complexity for MVP, but user asked for safety.
    # The user logic is: "I screwed up, go back".
    
    try:
        # 1. Close connections (Streamlit might hold one, but we closed ours)
        # 2. Copy backup -> live
        shutil.copy2(backup_path, config.DB_PATH)
        return True, "Database restored successfully. Please refresh."
    except Exception as e:
        return False, f"Restore failed: {e}"

def delete_database_backup(backup_id):
    """
    Deletes a backup: removes the physical file from disk and the record from the DB table.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT file_path, name FROM database_backups WHERE id = ?", (backup_id,))
    res = c.fetchone()

    if not res:
        conn.close()
        return False, "Backup record not found."

    file_path = Path(res[0])
    backup_name = res[1]

    # 1. Delete physical file (ignore if already missing)
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        conn.close()
        return False, f"Could not delete file: {e}"

    # 2. Remove DB record
    try:
        c.execute("DELETE FROM database_backups WHERE id = ?", (backup_id,))
        conn.commit()
    except Exception as e:
        conn.close()
        return False, f"Could not remove DB record: {e}"

    conn.close()
    return True, f"Backup '{backup_name}' deleted successfully."

def create_backup(user_name):
    return create_database_backup(user_name)

def get_analytics_data():
    """
    Aggregates data for Super Admin charts.
    """
    conn = get_connection()
    
    # 1. Status Distribution
    status_df = pd.read_sql("SELECT item_status, COUNT(*) as count FROM parts WHERE is_archived = 0 GROUP BY item_status", conn)
    
    # 2. Advisor Workload
    adv_df = pd.read_sql("SELECT service_advisor, item_status, COUNT(*) as count FROM parts WHERE is_archived = 0 AND service_advisor IS NOT NULL AND service_advisor != 'Unknown' GROUP BY service_advisor, item_status", conn)
    
    # 3. Car Down List
    cardown_df = pd.read_sql("SELECT item_no, item_description, customer_name, service_advisor, eta, last_updated FROM parts WHERE is_archived = 0 AND cardown = 'Yes' ORDER BY last_updated ASC", conn)
    
    # 4. Top Customers (By Active Orders)
    top_cust_df = pd.read_sql("SELECT customer_name, COUNT(*) as count FROM parts WHERE is_archived = 0 AND customer_name IS NOT NULL AND customer_name != '' GROUP BY customer_name ORDER BY count DESC LIMIT 10", conn)

    conn.close()
    
    return {
        'status_counts': status_df,
        'advisor_stats': adv_df,
        'cardown_cases': cardown_df,
        'top_customers': top_cust_df
    }

def get_problem_items(days_threshold=10):
    """
    Returns items that are problematic:
    - Status 'Back Order' OR 'Received'
    - Aging > threshold days
    """
    conn = get_connection()
    # optimized query
    # We need to compute aging.
    # For 'Received': days_in_stock
    # For 'Back Order': days since... creation? or last update?
    # Let's rely on Python logic for complex aging parsing if needed, but SQL is faster.
    # We have 'last_updated'. simpler proxy for 'Back Order': time since last update?
    # Or time since creation?
    # 'updates_log' contains the history.
    # Let's fetch candidates and filter in Python using utils.get_days_in_stock logic 
    # (which handles log parsing for 'Received').
    # For Back Order, maybe we just use (Now - last_updated)? Or (Now - Created)?
    # Let's use (Now - last_updated) as proxy for "No movement".
    
    query = """
        SELECT * FROM parts 
        WHERE is_archived = 0 
        AND item_status IN ('Back Order', 'Received')
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    problem_items = []
    
    if df.empty:
        return problem_items
        
    for _, row in df.iterrows():
        status = row['item_status']
        days = 0
        
        if status == 'Received':
            # Use strict "Days in Stock" logic
            days = utils.get_days_in_stock(row['updates_log'])
        else:
            # Back Order Aging
            # prioritized: back_order_original_date -> last_updated
            try:
                if row.get('back_order_original_date'):
                    # Use explicit date
                    start_date = pd.to_datetime(row['back_order_original_date'])
                else:
                    # Fallback
                    start_date = pd.to_datetime(row['last_updated'])
                    
                delta = datetime.now() - start_date
                days = delta.days
            except:
                days = 0
                
        if days > days_threshold:
            # Add to list
            item = row.to_dict()
            item['days_aging'] = days
            problem_items.append(item)
            
    return problem_items

def add_update_log(item_id, message, username):
    """
    Appends a log message to the updates_log field.
    """
    conn = get_connection()
    c = conn.cursor()
    # Log format: [YYYY-MM-DD HH:MM] User: Message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"\n[{timestamp}] {username}: {message}"
    
    try:
        c.execute("UPDATE parts SET updates_log = updates_log || ? WHERE id = ?", (log_entry, item_id))
        conn.commit()
    except Exception as e:
        print(f"Error adding log: {e}")
    finally:
        conn.close()

def add_notification(message, target_advisor_code=None):
    """
    Adds a notification to the notifications table.
    """
    # Skipping implementation for now if table doesn't exist or not used yet?
    # Or implement simply if needed. The error suggested it was called.
    # Check if 'notifications' table exists? Assume yes or handle gracefully.
    conn = get_connection() 
    c = conn.cursor()
    try:
        # Check if table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        if not c.fetchone():
            # Create if needed
            c.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read INTEGER DEFAULT 0,
                    target_user TEXT -- optional
                )
            ''')
            
        c.execute("INSERT INTO notifications (message, target_user) VALUES (?, ?)", (message, target_advisor_code))
        conn.commit()
    except Exception as e:
        print(f"Error adding notification: {e}")
    finally:
        conn.close()

def update_eta(item_id, new_eta, username="Admin"):
    """
    Updates ETA, Logs Change, and Emails Advisor.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Get current details for log and email
    # Also fetch Customer Name for context
    c.execute("SELECT item_no, item_description, service_advisor, eta, customer_name FROM parts WHERE id = ?", (item_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Item not found."
        
    item_no, desc, advisor, old_eta, customer = row
    
    # Check if changed (String comparison)
    if str(old_eta) == str(new_eta):
        conn.close()
        return True, "No change." # Return True to avoid error noise if same
        
    # Update DB
    c.execute("UPDATE parts SET eta = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?", (new_eta, item_id))
    conn.commit()
    conn.close()
    
    # Log
    log_msg = f"ETA updated from '{old_eta}' to '{new_eta}' by {username}"
    add_update_log(item_id, log_msg, username)
    add_notification(f"ETA Changed for {item_no}: {new_eta}", target_advisor_code=advisor)
    
    # Email
    if advisor and advisor != 'Unknown':
        recipients = get_user_emails_by_advisor_code(advisor)
        
        # Prepare "Table" Data for Bulk Notification Template
        # We construct a synthetic item dict to leverage the nice table formatting
        email_items = [{
            'item_no': item_no,
            'description': desc,
            'customer': customer,
            'old_eta': old_eta,
            'new_eta': new_eta,
            'updated_by': username,
            'status': 'ETA Update' # Context column
        }]
        
        for email, user in recipients:
             try:
                 # Re-use the bulk notification template for consistent design
                 mailer.send_bulk_notification(
                     email, 
                     email_items, 
                     title=f"ETA Update: {item_no}", 
                     advisor_name=user
                 )
             except Exception as e:
                 print(f"Error sending email: {e}")
             
    return True, "ETA updated."

def update_stock_date(item_id, new_date_str, username="Admin"):
    """
    Updates the custom_stock_date for an item.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Update
    log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {username}: Updated Stock Date to {new_date_str}"
    
    try:
        c.execute('''
            UPDATE parts
            SET custom_stock_date = ?,
                updates_log = updates_log || ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_date_str, log_entry, item_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating stock date: {e}")
        conn.close()
        return False, str(e)
        
    conn.close()
    return True, "Stock Date updated."

def update_back_order_date(item_id, new_date_str, username="Admin"):
    """
    Updates the Back Order Original Date.
    """
    print(f"DEBUG DB: Updating Item {item_id} BackOrderDate to '{new_date_str}'")
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE parts SET back_order_original_date = ? WHERE id = ?", (new_date_str, item_id))
        
        # Add Log Entry Manually (Safer than relying on external function which might use different connection logic)
        log_entry = f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {username}: Back Order Start Date set to {new_date_str}"
        c.execute("UPDATE parts SET updates_log = updates_log || ? WHERE id = ?", (log_entry, item_id))
        
        conn.commit()
        # Verify
        # Verify
        c.execute("SELECT back_order_original_date FROM parts WHERE id = ?", (item_id,))
        verify_row = c.fetchone()
        val = verify_row[0] if verify_row else "Row Not Found"
        print(f"DEBUG DB: Verify Update -> {val}")
        
        conn.close()
        return True, "Back Order Date updated."
    except Exception as e:
        conn.close()
        print(f"Error updating back order date: {e}")
        return False, str(e)
