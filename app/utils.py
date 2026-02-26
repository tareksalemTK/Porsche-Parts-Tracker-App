import re
import traceback
import pandas as pd
from datetime import datetime, timedelta

def clean_str(val):
    if pd.isna(val) or val == '':
        return ''
    return str(val).strip()

def clean_int(val):
    try:
        if pd.isna(val) or val == '':
            return 0
        return int(float(val))
    except:
        return 0

def calculate_two_weeks_eta():
    """Returns date string: Today + 14 days"""
    date = datetime.now() + timedelta(days=14)
    return date.strftime('%Y-%m-%d')

def smart_normalize_order(val):
    """
    Advanced Normalization.
    1. Removes 'Purchase Order', spaces.
    2. Handles '04' prefix -> '26PAG'.
    3. STRIPS zero padding within the alphanumeric string to ensure match.
       e.g. '26PAG000002' -> '26PAG2'
       e.g. '26PAG002'    -> '26PAG2'
    """
    s = clean_str(val).upper()
    s = re.sub(r'PURCHASE\s*ORDER', '', s)
    s = s.replace(' ', '')
    
    # Prefix handling
    if s.startswith('04'):
        s = '26PAG' + s[2:]
        
    # Zero Padding handling:
    # Look for pattern: [Letters][Zeros][Numbers]
    # or just [Letters][Numbers].
    # We want to canonicalize 'PAG0002' to 'PAG2'.
    
    # Regex to find embedded numbers
    # Split into parts
    # strict approach: if matches (STRING)(DIGITS), strip leading zeros from digits
    match = re.match(r'^([A-Z]+)(\d+)$', s)
    if match:
        prefix = match.group(1)
        number = match.group(2).lstrip('0')
        return f"{prefix}{number}"
    
    # If mixed like '26PAG002' -> '26PAG' is not just alpha.
    # Pattern: (Anything)(Digits)$
    match2 = re.match(r'^(.*?)(\d+)$', s)
    if match2:
        prefix = match2.group(1)
        number = match2.group(2).lstrip('0')
        return f"{prefix}{number}"
        
    return s

def normalize_order_no(val):
    # Wrapper for legacy or simple
    return smart_normalize_order(val)

def normalize_part_no(val):
    """
    Standardizes Part Numbers by removing spaces, dots, and dashes.
    Ensures '999.111' matches '999 111'.
    Handles Pandas float promotion (e.g. 123.0 -> 123).
    """
    s = clean_str(val)
    
    # Handle Float -> String conversion artifact
    if s.endswith('.0'):
        s = s[:-2]
        
    # Remove dots, spaces, dashes
    s = re.sub(r'[ \.\-]', '', s)
    return s.upper()

def parse_on_order(file_obj, service_advisor):
    """
    Parses 'On Order' sheet.
    Header Row: 0 (Line 1)
    """
    try:
        df = pd.read_excel(file_obj) # Header defaults to 0
        records = []
        for _, row in df.iterrows():
            # Mapping
            item_no = normalize_part_no(row.get('Item No.'))
            if not item_no: continue
            
            # ETA Logic: User requirement "automatically set for 2 weeks from upload"
            # We ignore the file's 'Expected Receipt Date' to enforce this rule.
            eta = calculate_two_weeks_eta()
            
            # Order No Cleaning
            # User mentioned "Reserved From" contains "Purchase Order 26PAG..."
            r_from = normalize_order_no(row.get('Reserved From'))
            r_for = normalize_order_no(row.get('Reserved For'))
            
            # Standard practice: Use Reserved From as Order No if present.
            # If r_from is empty, fallback to r_for? 
            # User report implies 'Reserved From' has the ID.
            order_no = r_from if r_from else r_for
            
            record = {
                'item_no': item_no,
                'item_description': clean_str(row.get('ReturnItemDescription')),
                'customer_no': clean_str(row.get('Customer No.')),
                'customer_name': clean_str(row.get('Customer Name')),
                'document_no': clean_str(row.get('Reserved For')), # Keep original for reference? or normalized?
                'order_no': order_no,   
                'service_advisor': service_advisor, # From User Selection
                'ordered_qty': clean_int(row.get('Quantity')),
                'in_transit_qty': 0, 
                'received_qty': 0,
                'eta': eta,
                'item_status': 'On Order',
                'remarks': '',
                'cardown': 'No', # Default
                'vin': ''
            }
            records.append(record)
        return records
    except Exception as e:
        traceback.print_exc()
        print(f"Error parsing On Order: {e}")
        return []

def parse_back_order(file_obj):
    """
    Parses 'Back Order' sheet.
    Header Row: Line 5 (skiprows=4)
    """
    try:
        df = pd.read_excel(file_obj, skiprows=4)
        records = []
        for _, row in df.iterrows():
            item_no = normalize_part_no(row.get('Part Number'))
            if not item_no: continue
            
            # Car Down Logic: 'x' -> 'Yes'
            cd_val = clean_str(row.get('Car Down'))
            cardown = 'Yes' if cd_val.lower() == 'x' else 'No'
            
            # Normalization Logic
            # Flexible Column Name for PO Reference
            possible_po_cols = ['PO Reference', 'P.O. Reference', 'PO Ref', 'P.O. Ref', 'Order No', 'Order Number']
            raw_po = ''
            for col in possible_po_cols:
                val = row.get(col)
                if not pd.isna(val) and str(val).strip():
                    raw_po = clean_str(val).upper()
                    break
            
            # Fallback: if raw_po is still empty, maybe it's in a column named 'Reference'?
            if not raw_po:
                raw_po = clean_str(row.get('Reference') or '').upper()
            
            # General Pattern Handler for "nn nnn" -> "26PAG{n}"
            # Regex: Start with 2 digits, space(s), then more digits.
            # Captures the suffix digits in group 1.
            match_pag = re.match(r'^\d{2}\s+(\d+)$', raw_po)
            if match_pag:
                 # Suffix is the second part (e.g. '062' or '045')
                 suffix = match_pag.group(1).lstrip('0')
                 po_ref = '26PAG' + suffix
            else:
                 # Standard / No change
                po_ref = raw_po
            
            # Apply standard normalization (cleanup spaces, etc.)
            po_ref = normalize_order_no(po_ref)
            
            record = {
                'item_no': item_no,
                'item_description': clean_str(row.get('Description')),
                'order_no': po_ref,
                'ordered_qty': clean_int(row.get('Backorder Quantity')),
                'eta': clean_str(row.get('ETA Date')),
                'next_info': clean_str(row.get('Next Information') or row.get('Next Info') or row.get('Next info') or row.get('Next Info from PAG')), 
                'cardown': cardown,
                'item_status': 'Back Order',
                # Defaults
                'in_transit_qty': 0,
                'received_qty': 0,
                'service_advisor': 'Unknown', 
                'document_no': '',
                'customer_no': '',
                'customer_name': '',
                'remarks': '',
                'vin': ''
            }
            records.append(record)
        return records
    except Exception as e:
        print(f"Error parsing Back Order: {e}")
        return []

def parse_invoiced(file_obj, manual_eta):
    """
    Parses 'Invoiced' sheet.
    Dynamically finds the header row by searching for 'Order No.' or 'ordered'.
    """
    try:
        # 1. Read first chunk to find header
        # Read roughly 60 rows (typical range is 49-51)
        temp_df = pd.read_excel(file_obj, header=None, nrows=60)
        
        header_row_idx = None
        for idx, row in temp_df.iterrows():
            # Robust conversion: ensure everything is a lower-case string
            row_str = [str(x).lower() for x in row.values]
            
            # signature keywords
            if any("order no" in s for s in row_str) and any("ordered" in s for s in row_str):
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            # Fallback to 48 (Line 49) if not found
            header_row_idx = 48
            
        # 2. Read actual data
        file_obj.seek(0)
        df = pd.read_excel(file_obj, skiprows=header_row_idx)
        
        # 3. Clean empty/junk rows between header and data
        # Often merged headers leave an empty row or a row with just sub-headers.
        # Check first row. If 'No.' is empty/NaN, drop it.
        if not df.empty:
            first_val = str(df.iloc[0].get('No.', ''))
            second_val = str(df.iloc[0].get('Order No.', ''))
            if first_val == 'nan' and second_val == 'nan':
                 df = df.iloc[1:]
                 
        records = []
        for _, row in df.iterrows():
            item_no = normalize_part_no(row.get('No.'))
            if not item_no: continue
            
            # Flexible column getting
            qty_ordered = clean_int(row.get('ordered')) or clean_int(row.get('Qty. Ordered'))
            qty_delivered = clean_int(row.get('delivered')) or clean_int(row.get('Qty. Delivered'))
            cust_name = clean_str(row.get('Cust. Name')) or clean_str(row.get('Customer Name')) or clean_str(row.get('Source Of Demande Cust. Name'))
            
            record = {
                'item_no': item_no,
                'order_no': clean_str(row.get('Order No.')),
                'in_transit_qty': qty_delivered, # Logic: In Transit = What is being shipped (Delivered column)
                'received_qty': qty_delivered,   # Passed to Update Logic as 'received_qty' key (for existing updates)
                'eta': manual_eta,
                'item_status': 'Invoiced', # Initial logic uses this but overridden by DB logic ('In Transit')
                'ordered_qty': qty_ordered,
                'item_description': clean_str(row.get('Description')), 
                'service_advisor': 'Unknown',
                'cardown': 'No',
                'document_no': '',
                'customer_no': str(row.get('Source Of Demande', '')), 
                'customer_name': cust_name,
                'remarks': '',
                'vin': ''
            }
            records.append(record)
        return records
    except Exception as e:
        print(f"Error parsing Invoiced: {e}")
        return []

def parse_log_to_df(log_text):
    """
    Parses the updates_log string into a DataFrame.
    Format: \n[YYYY-MM-DD HH:MM] User: Action
    """
    if not log_text:
        return pd.DataFrame(columns=['Timestamp', 'User', 'Action'])
    
    # regex pattern
    pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (.*?): (.*)'
    matches = re.findall(pattern, log_text)
    
    data = []
    for m in matches:
        data.append({'Timestamp': m[0], 'User': m[1], 'Action': m[2]})
        
    return pd.DataFrame(data)

def get_aging_text(log_text, status, custom_stock_date=None, back_order_date=None, received_date=None):
    """
    Returns formatted aging string based on status.
    - Received: Days since 'Received Stock', or custom_stock_date if provided -> "IS X days"
    - Back Order: Days since 'Uploaded (Source: BackOrder)' or back_order_date if provided -> "B.O. X days"
    """
    if not log_text and not custom_stock_date and not back_order_date and not received_date:
        return ""
        
    try:
        now = datetime.now()
        
        if status in ['Received', 'Partially Received']:
            # Priority 1: Custom Date
            if custom_stock_date:
                start_date = None
                try:
                    if isinstance(custom_stock_date, str):
                        start_date = datetime.strptime(custom_stock_date.split()[0], '%Y-%m-%d')
                    elif hasattr(custom_stock_date, 'date'):
                        d = custom_stock_date
                        if isinstance(d, datetime):
                            start_date = d
                        else:
                            start_date = datetime(d.year, d.month, d.day)
                except:
                    start_date = now
                if start_date:    
                    days = (now - start_date).days
                    return f"IS {max(0, days)} days"
            
            # Priority 2: Precise DB Timestamp (NEW OPTIMIZATION)
            if received_date:
                try:
                    if isinstance(received_date, str):
                        # Might look like '2026-02-26 09:50:00'
                        clean_str_date = received_date.split(' ')[0]
                        start_date = datetime.strptime(clean_str_date, '%Y-%m-%d')
                    elif hasattr(received_date, 'date'):
                        start_date = received_date
                    else:
                        start_date = None
                        
                    if start_date:
                        days = (now - start_date).days
                        return f"IS {max(0, days)} days"
                except Exception as e:
                    pass

            # Priority 3 (Fallback): Slow Regex parsing
            if log_text:
                matches = re.findall(r'\[(\d{4}-\d{2}-\d{2}).*?\].*?eceived', log_text)
                if matches:
                     last_date = datetime.strptime(matches[-1], '%Y-%m-%d')
                     days = (now - last_date).days
                     return f"IS {max(0, days)} days"
            
            return "IS 0 days"
        
        elif status == 'Back Order':
            # Priority: Custom Back Order Date > Log Entry
            if back_order_date:
                start_date = None
                try:
                    if isinstance(back_order_date, str):
                         if not back_order_date.strip() or back_order_date.lower() == 'none' or back_order_date.lower() == 'nat': 
                             raise ValueError
                         start_date = datetime.strptime(back_order_date.split()[0], '%Y-%m-%d')
                    elif hasattr(back_order_date, 'date'):
                        d = back_order_date
                        if isinstance(d, datetime):
                            start_date = d
                        else:
                            start_date = datetime(d.year, d.month, d.day)
                except Exception as e:
                     # print(f"Date Parse Error: {e}")
                     start_date = None
                
                if start_date:
                    days = (now - start_date).days
                    return f"B.O. {max(0, days)} days" if days >= 0 else "B.O. 0 days"

            # Find the FIRST log entry date (Upload date)
            # Typically regex: \[YYYY-MM-DD
            matches = re.findall(r'\[(\d{4}-\d{2}-\d{2})', log_text)
            if matches:
                first_date = datetime.strptime(matches[0], '%Y-%m-%d')
                days = (now - first_date).days
                return f"B.O. {max(0, days)} days" if days >= 0 else "B.O. 0 days"
                
    except Exception as e:
        # print(f"Aging error: {e}") 
        pass
    
    return ""

def get_days_in_stock(log_text):
    # Backward compatibility wrapper if needed, or deprecate
    # For now, return int for sorting if possible? 
    # But new requirement asks for text.
    # We will remove this or update it to return JUST the int for 'Received' if strictly needed elsewhere.
    # let's keep it behaving as "Days in Stock" (IS) count for now to avoid breaking other logic
    # until fully switched.
    s = get_aging_text(log_text, 'Received')
    if 'IS' in s:
        try:
            return int(s.split()[1])
        except:
            return 0
    return 0
        

