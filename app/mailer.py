import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import traceback

import config

# --- Configuration ---
# Use environment variables for security in production.
# For local dev/testing, you might set defaults or use a .env file loader (python-dotenv).
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "tmaher@porscheleb.com")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "tottlf00722")

# Dummy mapping for MVPs
ADVISOR_EMAILS = {
    "EMA": "ema@example.com",
    "EMB": "emb@example.com",
    "EMC": "emc@example.com",
    "B&P": "bnp@example.com",
    "OTC": "otc@example.com",
    "Unknown": "admin@example.com"
}

def get_advisor_email(advisor_code):
    return ADVISOR_EMAILS.get(advisor_code, "admin@example.com")

def send_email(receiver_email, subject, body_html):
    """
    Sends an HTML email using SMTP.
    """
    if not receiver_email:
        print("Skipping email: No receiver specified.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body_html, 'html'))

    try:
        # Production SMTP
        # server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) # For 465
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email to {receiver_email}: {e}")
        # traceback.print_exc()
        return False

import pandas as pd # Needed for table formatting

import base64

def get_base64_logo():
    """
    Tries to load the Porsche logo from assets and convert to base64.
    """
    try:
        logo_path = config.ASSETS_DIR / "toppng.com-porsche-logo-black-text-png-2000x238.png"
        if logo_path.exists():
            with open(logo_path, "rb") as img_file:
                b64_string = base64.b64encode(img_file.read()).decode('utf-8')
                return f"data:image/png;base64,{b64_string}"
    except Exception as e:
        print(f"Error loading logo: {e}")
    return None

def send_bulk_notification(advisor_email, items, title="Parts Notification", advisor_name=None, custom_message=None):
    """
    Sends a bulk email to one advisor with a list of items.
    """
    if not items or not advisor_email:
        return
        
    # Get First Name for greeting
    first_name = "Advisor"
    if advisor_name:
         # "Gaby Zeidan" -> "Gaby"
         first_name = advisor_name.strip().split(' ')[0].capitalize()
    
    # Create HTML Table
    df = pd.DataFrame(items)
    
    # User Request: Show ALL columns except specific blacklist
    BLACKLIST = [
        'updates_log', 'log', 'is_archived', 'posted_by', 'posted_at', 
        'source_file_type', 'id', 'advisor', 'shipment_ref'
    ]
    
    # 1. Filter columns
    valid_cols = [c for c in df.columns if c not in BLACKLIST]
    df = df[valid_cols]
    
    # 2. Rename columns (Title Case, underscore to space)
    preferred_order = [
         'item_no', 'item_description', 'description', 
         'status', 'item_status', 
         'notification_type', # Special
         'order_no', 'ordered_qty', 
         'document_no', 'customer_no', 'customer_name',
         'eta', 'cardown', 'duration'
    ]
    
    ordered_cols = []
    for k in preferred_order:
        if k in df.columns:
            ordered_cols.append(k)
            
    for k in df.columns:
        if k not in ordered_cols:
            ordered_cols.append(k)
            
    df = df[ordered_cols]
    
    # Rename for display
    rename_map = {}
    for c in df.columns:
        if c == 'item_no': rename_map[c] = 'Item No'
        elif c == 'item_description': rename_map[c] = 'Description'
        elif c == 'customer_name': rename_map[c] = 'Customer'
        elif c == 'document_no': rename_map[c] = 'Doc No'
        elif c == 'duration': rename_map[c] = 'Duration'
        else:
            rename_map[c] = c.replace('_', ' ').title()
            
    df = df.rename(columns=rename_map)
    
    # --- STYLING LOGIC ---
    # Apply colors to cells matching the Dashboard colors
    
    def highlight_cells(val):
        # Helper for color logic (same as main.py)
        if isinstance(val, str):
            # Status Colors
            if val == 'Back Order': return 'background-color: #ef5350; color: white'
            elif val == 'On Order': return 'background-color: #ff9800; color: black'
            elif val == 'In Transit': return 'background-color: #ffe0b2; color: black'
            elif val == 'Partially Received': return 'background-color: #dcedc8; color: black'
            elif val == 'Reordered': return 'background-color: #ab47bc; color: white'
            elif val == 'Received': return 'background-color: #2e7d32; color: white'
            
            # Duration Colors (heuristic check)
            # "IS 5 days", "B.O. 10 days"
            import re
            if 'days' in val:
                match = re.search(r'\d+', val)
                if match:
                    days = int(match.group())
                    if days <= 3: return 'background-color: #dcedc8; color: black'
                    elif days <= 9: return 'background-color: #fff176; color: black'
                    else: return 'background-color: #ef5350; color: white'
        return ''

    # Use Pandas Styler
    styler = df.style.map(highlight_cells)
    
    # Render HTML from Styler
    # We strip the default style to inject our own class, but keep inline styles from map
    table_src = styler.to_html(index=False, border=0, table_attributes='class="content-table"')
    
    # The to_html from Styler includes a lot of default CSS in <style> block which might conflict or be ugly.
    # We want to keep ONLY the inline styles we added.
    # "uuid" filtering is hard.
    # Alternative: Manual row iteration is safer for clean email HTML.
    
    # Let's use Manual Generation to ensure it matches our Premium Template perfect + Colors
    
    # Re-using df
    cols = df.columns.tolist()
    rows_html = ""
    
    for _, row in df.iterrows():
        rows_html += "<tr>"
        for col in cols:
            val = row[col]
            style = highlight_cells(val)
            val_str = str(val) if pd.notna(val) else ""
            rows_html += f'<td style="{style}">{val_str}</td>'
        rows_html += "</tr>"
        
    header_html = "<thead><tr>" + "".join([f"<th>{c}</th>" for c in cols]) + "</tr></thead>"
    table_html = f'<table class="content-table" border="0" cellpadding="0" cellspacing="0">{header_html}<tbody>{rows_html}</tbody></table>'

    # --- WHITE THEME TEMPLATE ---
    logo_src = get_base64_logo()
    # If no logo, text. If logo, place it.
    
    logo_block = f'<img src="{logo_src}" alt="Porsche" width="300" style="display: block; margin: 0 auto;">' if logo_src else '<h1 style="color:black; text-align:center;">PORSCHE</h1>'
    
    # Custom Message Logic
    default_msg = "The following parts in the tracker have been updated:"
    message_content = custom_message if custom_message else default_msg
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #ffffff; margin: 0; padding: 0; }}
        .email-container {{ width: 100%; max-width: 1200px; margin: 20px auto; background-color: #ffffff; padding: 15px; box-sizing: border-box; }}
        
        /* Header: White Background, Centered Logo */
        .header {{ padding: 20px 0; text-align: center; border-bottom: 2px solid #eeeeee; }}
        
        .content {{ padding: 30px 0; }}
        .footer {{ background-color: #f9f9f9; color: #666666; padding: 20px; text-align: center; font-size: 12px; border-top: 1px solid #eeeeee; }}
        
        h2 {{ color: #000000; margin-top: 0; font-weight: 300; }}
        p {{ color: #333333; line-height: 1.6; font-size: 15px; }}
        
        /* Table Styling */
        .content-table {{ border-collapse: collapse; margin: 20px 0; font-size: 13px; min-width: 100%; width: 100%; border: 1px solid #e0e0e0; }}
        
        /* Header: GREY Background */
        .content-table thead tr {{ background-color: #555555; color: #ffffff; text-align: left; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        .content-table th, .content-table td {{ padding: 8px 6px; border-bottom: 1px solid #e0e0e0; white-space: nowrap; }}
        .content-table tbody tr:nth-of-type(even) {{ background-color: #f8f8f8; }}
        
        /* Column Lines (Vertical Borders) */
        .content-table th, .content-table td {{ border-right: 1px solid #e0e0e0; }}
        .content-table th:last-child, .content-table td:last-child {{ border-right: none; }}
        
        a.button {{ display: inline-block; background-color: #B12B28; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 20px; }}
    </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                 {logo_block}
            </div>
            <div class="content">
                <h2>Hello {first_name},</h2>
                <p>{message_content}</p>
                <div style="overflow-x:auto;">
                    {table_html}
                </div>
                <br>
                <p>Please log in to the Dashboard to review.</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 PCL Parts Reservation Tracker. Internal Use Only.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    print(f"Sending bulk email to {advisor_email} with {len(items)} items...")
    send_email(advisor_email, title, html_body)

def send_stale_stock_warning(advisor_email, items, advisor_name=None):
    """
    Sends a WARNING email for stale stock items.
    """
    if not items or not advisor_email:
        return
        
    first_name = "Advisor"
    if advisor_name:
         first_name = advisor_name.strip().split(' ')[0].capitalize()
         
    # Prepare Table
    df = pd.DataFrame(items)
    
    # Select cols
    cols = ['item_no', 'item_description', 'days_in_stock', 'customer_name', 'order_no', 'document_no']
    # Filter if exist
    valid = [c for c in cols if c in df.columns]
    df = df[valid]
    
    # Rename
    rename_map = {
        'item_no': 'Item No',
        'item_description': 'Description',
        'days_in_stock': 'Days Waiting',
        'customer_name': 'Customer',
        'order_no': 'Order No',
        'document_no': 'Doc No'
    }
    df = df.rename(columns=rename_map)
    
    # Render with Red Highlights for Days Waiting
    rows_html = ""
    col_list = df.columns.tolist()
    
    for _, row in df.iterrows():
        rows_html += "<tr>"
        for col in col_list:
            val = row[col]
            style = ""
            if col == 'Days Waiting':
                style = "color: #B12B28; font-weight: bold;"
            rows_html += f'<td style="{style}">{val}</td>'
        rows_html += "</tr>"
        
    header_html = "<thead><tr>" + "".join([f"<th>{c}</th>" for c in col_list]) + "</tr></thead>"
    table_html = f'<table class="content-table" border="0" cellpadding="0" cellspacing="0">{header_html}<tbody>{rows_html}</tbody></table>'
    
    logo_src = get_base64_logo()
    logo_block = f'<img src="{logo_src}" alt="Porsche" width="300" style="display: block; margin: 0 auto;">' if logo_src else '<h1 style="color:black; text-align:center;">PORSCHE</h1>'
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #ffffff; margin: 0; padding: 0; }}
        .email-container {{ width: 100%; max-width: 1200px; margin: 20px auto; background-color: #ffffff; padding: 15px; border-top: 5px solid #d32f2f; box-sizing: border-box; }} /* Red Top Border for Warning */
        
        .header {{ padding: 20px 0; text-align: center; border-bottom: 2px solid #eeeeee; }}
        .content {{ padding: 30px 0; }}
        .footer {{ background-color: #f9f9f9; color: #666666; padding: 20px; text-align: center; font-size: 12px; border-top: 1px solid #eeeeee; }}
        
        h2 {{ color: #d32f2f; margin-top: 0; font-weight: 600; }} /* Red Header */
        p {{ color: #333333; line-height: 1.6; font-size: 15px; }}
        
        .content-table {{ border-collapse: collapse; margin: 20px 0; font-size: 13px; min-width: 100%; width: 100%; border: 1px solid #e0e0e0; }}
        .content-table thead tr {{ background-color: #d32f2f; color: #ffffff; text-align: left; font-weight: 600; text-transform: uppercase; }}
        .content-table th, .content-table td {{ padding: 8px 6px; border-bottom: 1px solid #e0e0e0; white-space: nowrap; }}
        .content-table tbody tr:nth-of-type(even) {{ background-color: #f8f8f8; }}
        
    </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                 {logo_block}
            </div>
            <div class="content">
                <h2>⚠️ Action Required: Stale Stock Warning</h2>
                <p>Hello {first_name},</p>
                <p>The following parts have been in stock for <strong>more than 7 days</strong> and have not yet been picked up.</p>
                <p>Please contact the customer immediately to schedule an appointment or arrange pickup.</p>
                <div style="overflow-x:auto;">
                    {table_html}
                </div>
                <br>
                <p>Please log in to the Dashboard to update the status.</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 PCL Parts Reservation Tracker. Internal Use Only.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    print(f"Sending WARNING email to {advisor_email}...")
    send_email(advisor_email, "⚠️ Reminder: Parts Waiting > 7 Days", html_body)
