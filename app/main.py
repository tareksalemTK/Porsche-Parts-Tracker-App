import streamlit as st
import pandas as pd
import db
import utils
import config
import time
import io
import mailer
from datetime import datetime


# --- Config ---
st.set_page_config(page_title="PCL Parts Reservation Tracker", layout="wide")

# --- Premium Porsche UI Styling ---
def apply_premium_styles():
    st.markdown("""
    <style>
        /* Modern Apple/Porsche Typography & Spacing */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f7f7f9;
        }
        
        /* Premium Card style for tabs and main containers */
        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
            border: 1px solid rgba(0,0,0,0.05);
        }

        /* Refined Primary Buttons matching Porsche Red */
        .stButton button[kind="primary"] {
            background-color: #D5001C !important;  /* True Porsche Red */
            color: white !important;
            border: none !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1.5rem !important;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 4px 6px rgba(213, 0, 28, 0.2) !important;
        }
        
        .stButton button[kind="primary"]:hover {
            background-color: #b00017 !important;
            box-shadow: 0 6px 12px rgba(213, 0, 28, 0.3) !important;
            transform: translateY(-1px) !important;
        }
        
        /* Secondary Buttons */
        .stButton button[kind="secondary"] {
            background-color: #ffffff !important;
            color: #333333 !important;
            border: 1px solid #e0e0e0 !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        
        .stButton button[kind="secondary"]:hover {
            border-color: #D5001C !important;
            color: #D5001C !important;
        }

        /* Sophisticated Dataframes/Tables */
        div[data-testid="stDataFrame"] {
            border-radius: 8px !important;
            border: 1px solid #eaebec !important;
            overflow: hidden !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.02) !important;
        }
        
        /* Headers & Typographic Scale */
        h1, h2, h3 {
            color: #1a1a1a !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em !important;
        }
        
        h1 { font-size: 2.2rem !important; margin-bottom: 1.5rem !important; }
        h2 { font-size: 1.6rem !important; margin-bottom: 1rem !important; }
        h3 { font-size: 1.2rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.05em !important; color: #666 !important; }

        /* Sleek Status Alerts/Toasts */
        .stAlert {
            border-radius: 8px !important;
            border-left-width: 4px !important;
        }
        
        /* Minimalist text inputs */
        .stTextInput input, .stSelectbox select {
            border-radius: 6px !important;
            border: 1px solid #e0e0e0 !important;
            padding: 10px 14px !important;
            background-color: #fbfbfb !important;
            transition: border-color 0.2s ease !important;
        }
        
        .stTextInput input:focus, .stSelectbox select:focus {
            border-color: #D5001C !important;
            box-shadow: 0 0 0 1px #D5001C !important;
        }
        
        /* Tabs Underline Style */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2rem;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 3rem;
            white-space: nowrap;
            background-color: transparent !important;
        }
        
        .stTabs [aria-selected="true"] {
            color: #D5001C !important;
            border-bottom-color: #D5001C !important;
            border-bottom-width: 3px !important;
        }
    </style>
    """, unsafe_allow_html=True)

apply_premium_styles()

# --- Database Init ---
db.init_db()

# --- Session State ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'user_type' not in st.session_state:
    st.session_state['user_type'] = None
if 'advisor_code' not in st.session_state:
    st.session_state['advisor_code'] = None

# --- Auth Functions ---
# --- Auth Functions ---
def login():
    # Centered Layout with Logo
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.image(str(config.ASSETS_DIR / "toppng.com-porsche-logo-black-text-png-2000x238.png"), use_container_width=True)
        st.markdown("<h2 style='text-align: center;'>Login</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            submit = st.form_submit_button("Login", use_container_width=True)
        
        if submit:
            user = db.verify_user(username, password)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user['username']
                st.session_state['user_type'] = user['user_type']
                st.session_state['advisor_code'] = user['service_advisor_code']
                st.success(f"Welcome {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = None
    st.session_state['user_type'] = None
    st.session_state['advisor_code'] = None
    st.rerun()

# --- Notifications Component ---
def render_notifications(as_popover=False, key_suffix=""):
    # Get unread
    notifs = db.get_notifications_for_user(
        None, # User ID not strictly tracked in session yet beyond username
        st.session_state.get('user_type', ''),
        st.session_state.get('advisor_code', '')
    )
    
    count = len(notifs)
    label = f"🔔 Notifications ({count})" if count > 0 else "🔔 Notifications"

    def _content():
        if not notifs:
            st.caption("No new notifications.")
        else:
            if st.button("Clear All", key=f"clear_all_notifs_{key_suffix}"):
                db.mark_all_notifications_read()
                st.rerun()

            for n in notifs:
                col_a, col_b = st.columns([0.9, 0.1])
                with col_a:
                    st.info(f"[{n['created_at'][:16]}] {n['message']}")
                with col_b:
                    if st.button("❌", key=f"notif_{n['id']}_{key_suffix}", help="Dismiss"):
                        db.mark_notification_read(n['id'])
                        st.rerun()

    # Render as popover or expander
    if as_popover and hasattr(st, 'popover'):
        with st.popover(label, use_container_width=True):
            _content()
    else:
        with st.expander(label, expanded=False):
            _content()

# --- Admin Components ---
def admin_upload_section():
    st.subheader("📁 Data Upload")
    tab1, tab2, tab3 = st.tabs(["On Order", "Back Order", "Invoiced"])
    # ... (rest of function unchanged, skipping for brevity in this replace block as distinct from dashboard logic)
    # Actually I need to be careful with replace_file_content chunk size.
    # The user asked to modify login AND dashboard. They are far apart in the file.
    # I should do TWO replace calls to be safe and accurate.
    # This block targets login() (lines 28-56 approx) so I will stop here and do dashboard separately.
    pass 

def render_super_admin_dashboard():
    st.markdown("### 📊 Executive Dashboard")
    
    # metrics = db.get_dashboard_metrics()
    # User removed specific metrics (Value Reserved). 
    # Let's keep Active Orders and Stock Awaiting Pickup? User said "remove value reserved".
    # User said "remove car down cases" (chart or metric? "Remove car down cases" implies the metric too or just chart? usually chart, but to be safe I will keep the metric if useful, but user said remove. Let's remove the visual clutter).
    # User specifically said: "remove value reserved", "remove top customer chart", "remove inventory composition", "remove car down cases".
    # Remaining Metrics: Active Orders, Stock Awaiting Pickup.
    
    metrics = db.get_dashboard_metrics()
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total Active Orders", metrics.get('active_orders', 0), help="Total items currently being tracked.")
    with c2:
        st.metric("Stock Awaiting Pickup", metrics.get('received_count', 0), help="Items with status 'Received'.")
    
    st.divider()
    
    # --- Live Charts ---
    # User kept Advisor Workload? "remove the top customer chart", "remove inventory composition", "remove car down cases".
    # Did NOT say remove Advisor Workload. So we keep it.
    
    try:
        analytics = db.get_analytics_data()
        
        st.subheader("📉 Advisor Workload")
        adv_stats = analytics.get('advisor_stats')
        if not adv_stats.empty:
            pivot_df = adv_stats.pivot(index='service_advisor', columns='item_status', values='count').fillna(0)
            st.bar_chart(pivot_df, stack=True)
        else:
            st.caption("No data.")
            
    except Exception as e:
        st.error(f"Error: {e}")
        
    st.divider()
    
    # --- PROBLEM ITEMS (Aging > 10 Days) ---
    st.subheader("⚠️ Problem Items (> 10 Days)")
    st.caption("Items in 'Back Order' or 'Received' status that have not moved for over 10 days.")
    
    problems = db.get_problem_items(days_threshold=10)
    
    if problems:
        p_df = pd.DataFrame(problems)
        
        # Display specific cols
        show_cols = ['item_no', 'item_description', 'item_status', 'days_aging', 'service_advisor', 'customer_name']
        
        st.dataframe(
            p_df[show_cols].style.map(lambda x: 'color: #B12B28; font-weight: bold;', subset=['days_aging']),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ No problematic aging items found (All < 10 days).")

    st.divider()
    
    # --- TOP PARTS ---
    # User requested to keep this or re-add it.
    st.subheader("📊 Top Ordered Parts")
    top_parts = db.get_top_ordered_parts(5)
    if not top_parts.empty:
        st.bar_chart(top_parts.set_index('item_no')['frequency'], color="#B12B28") 
    else:
        st.caption("No data available.")
        
    st.divider()
    
    # --- Backup & Restore Section ---
    st.subheader("🛡️ System Safety & Backups")
    bc1, bc2 = st.columns([1, 2])
    
    with bc1:
        st.markdown("**Create Restore Point**")
        st.caption("Save the current state.")
        if st.button("💾 Create Backup Now"):
             success, msg = db.create_backup(st.session_state.get('username'))
             if success:
                 st.success(msg)
                 time.sleep(1)
                 st.rerun()
             else:
                 st.error(msg)
                 
    with bc2:
        st.markdown("**Rewind System**")
        st.caption("Restore database to a previous point.")
        
        backups = db.get_available_backups()
        
        if backups:
            for b in backups:
                # b is a dict: {id, name, timestamp, file_path, created_by}
                c_name, c_restore, c_delete = st.columns([3, 1, 0.5])
                with c_name:
                    st.text(f"{b['created_by']} — {b['timestamp']}")
                with c_restore:
                    if st.button("Restore", key=f"btn_restore_{b['id']}"):
                        success, msg = db.restore_database_backup(b['id'])
                        if success:
                            st.success(msg)
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(msg)
                with c_delete:
                    if st.button("❌", key=f"btn_del_backup_{b['id']}", help="Delete this backup permanently"):
                        success, msg = db.delete_database_backup(b['id'])
                        if success:
                            st.toast(msg, icon="🗑️")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("No backups found.")


# --- Admin Components ---
def admin_upload_section():
    st.subheader("📁 Data Upload")
    tab1, tab2, tab3 = st.tabs(["On Order", "Back Order", "Invoiced"])
    
    # 1. On Order
    with tab1:
        st.info("Upload 'On Order' File. Select the target Service Advisor.")
        up_file = st.file_uploader("Choose Excel File", type=['xlsx'], key='on_order_up')
        advisor = st.selectbox("Assign to Service Advisor", ["EMA GilbetZ", "EMB TonyR", "EMC JackS", "B&P", "OTC"])
        status_placeholder = st.empty()
        
        if st.button("Process On Order"):
            if up_file:
                status_placeholder.markdown("<p style='color: red; font-weight: bold;'>Processing 'On Order' upload... Please wait (Do not double-click).</p>", unsafe_allow_html=True)
                start_t = time.time()
                data = utils.parse_on_order(up_file, advisor)
                count = 0
                
                # Buffer for email
                # For On Order, we know the advisor is the same for all (selected in UI)
                on_order_items = []
                
                for record in data:
                    res = db.insert_part_record(record, 'OnOrder')
                    if res and isinstance(res, list):
                        on_order_items.extend(res)
                    count += 1
                
                # Email Notification
                if on_order_items:
                    recipients = db.get_user_emails_by_advisor_code(advisor)
                    for email, username in recipients:
                        mailer.send_bulk_notification(email, on_order_items, title=f"New On Order Parts ({len(on_order_items)})", advisor_name=username)
                
                # System Notification
                db.add_notification(f"New 'On Order' file uploaded for {advisor} ({count} items).", target_advisor_code=advisor)
                status_placeholder.empty()
                st.success(f"Processed {count} records in {time.time()-start_t:.2f}s")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Please upload a file.")

    # 2. Back Order
    with tab2:
        st.info("Upload 'Back Order' File (Starts Line 5).")
        up_file_bo = st.file_uploader("Choose Excel File", type=['xlsx'], key='back_order_up')
        
        # Date Input for Back Order Start Date
        st.caption("📅 Specify when these items went on back order (defaults to today):")
        back_order_date = st.date_input("Back Order Start Date", value=datetime.now().date(), key='bo_date')
        
        bo_status_placeholder = st.empty()
        
        if st.button("Process Back Order"):
            if up_file_bo:
                bo_status_placeholder.markdown("<p style='color: red; font-weight: bold;'>Processing 'Back Order' upload... Please wait (Do not double-click).</p>", unsafe_allow_html=True)
                data = utils.parse_back_order(up_file_bo)
                count = 0
                
                # Buffer IDs/Notifs (Group by Advisor)
                updates_by_advisor = {}
                
                # Convert date to string format for database
                from datetime import date
                if isinstance(back_order_date, (datetime, date)):
                    bo_date_str = back_order_date.strftime('%Y-%m-%d')
                else:
                    bo_date_str = str(back_order_date)
                
                for record in data:
                    # Add back order date to record
                    record['back_order_date'] = bo_date_str
                    
                    res = db.insert_part_record(record, 'BackOrder')
                    if res and isinstance(res, list):
                        for notif in res:
                             adv = notif['advisor']
                             if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                             updates_by_advisor[adv].append(notif)
                    count += 1
                
                # Send Emails
                for adv_code, items in updates_by_advisor.items():
                    recipients = db.get_user_emails_by_advisor_code(adv_code)
                    for email, username in recipients:
                        mailer.send_bulk_notification(email, items, title="Parts Status Update: Back Order", advisor_name=username)
                
                # Notification
                db.add_notification(f"New 'Back Order' file uploaded ({count} items).")
                bo_status_placeholder.empty()
                st.success(f"Processed {count} records and triggered email notifications.")
                
                # Display Results Table
                all_processed_items = []
                for adv, items in updates_by_advisor.items():
                    all_processed_items.extend(items)
                    
                if all_processed_items:
                    st.subheader("📋 Processed Items & Aging")
                    res_df = pd.DataFrame(all_processed_items)
                    
                    cols_show = ['item_no', 'description', 'advisor', 'status', 'duration']
                    cols_final = [c for c in cols_show if c in res_df.columns]
                    
                    res_view = res_df[cols_final].rename(columns={
                        'item_no': 'Item No',
                        'description': 'Description',
                        'advisor': 'Advisor',
                        'status': 'Status',
                        'duration': 'Duration'
                    })
                    
                    def highlight_duration(val):
                        if pd.isna(val) or val == '': return ''
                        txt = str(val)
                        import re
                        match = re.search(r'\d+', txt)
                        if match:
                            days = int(match.group())
                            if days <= 3: return 'background-color: #dcedc8; color: black'
                            elif days <= 9: return 'background-color: #fff176; color: black'
                            else: return 'background-color: #ef5350; color: white'
                        return ''

                    st.dataframe(
                        res_view.style.map(highlight_duration, subset=['Duration']),
                        use_container_width=True,
                        hide_index=True
                    )


                
                # time.sleep(1) # Removed sleep to let user see table
                # st.rerun() # Removed rerun to let user see table. User can manually navigate away.


    # 3. Shipment Management (Invoiced V2)
    with tab3:
        st.subheader("📦 Shipment Management")
        
        mode = st.radio("Mode", ["1️⃣ Upload Notification (In Transit)", "2️⃣ Review & Receive Stock", "3️⃣ Shipment Overview & ETA"], horizontal=True)
        
        if mode == "1️⃣ Upload Notification (In Transit)":
            st.info("Upload 'Invoiced/Shipping' File. Items will be marked as **In Transit**.")
            up_file_inv = st.file_uploader("Choose Excel File", type=['xlsx'], key='invoiced_up')
            manual_eta = st.date_input("Set ETA for this Shipment").strftime('%Y-%m-%d')
            
            ship_status_placeholder = st.empty()
            
            if st.button("Process Shipment Notification"):
                if up_file_inv:
                    ship_status_placeholder.markdown("<p style='color: red; font-weight: bold;'>Processing Shipment... Please wait (Do not double-click).</p>", unsafe_allow_html=True)
                    # Pass context: Shipment Name
                    shipment_name = up_file_inv.name
                    data = utils.parse_invoiced(up_file_inv, manual_eta)
                    
                    count = 0
                    updates_by_advisor = {}
                    
                    for record in data:
                        # Append shipment ref to record for DB
                        record['shipment_ref'] = shipment_name
                        # Note: 'received_qty' key in record will be mapped to 'in_transit_qty' by DB logic
                        res = db.insert_part_record(record, 'Invoiced') 
                        
                        if res and isinstance(res, list):
                            for notif in res:
                                 adv = notif['advisor']
                                 if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                                 updates_by_advisor[adv].append(notif)
                        
                        count += 1
                        
                    # Send Emails
                    for adv_code, items in updates_by_advisor.items():
                        recipients = db.get_user_emails_by_advisor_code(adv_code)
                        for email, username in recipients:
                            mailer.send_bulk_notification(email, items, title=f"Shipment {shipment_name} - In Transit", advisor_name=username)
                        
                    db.add_notification(f"New Shipment '{shipment_name}' In Transit ({count} items).")
                    ship_status_placeholder.empty()
                    st.success(f"Processed {count} records. Items are now 'In Transit'. Go to 'Review & Receive' when they arrive.")
                    time.sleep(2)
                    st.rerun()
        
        elif mode == "2️⃣ Review & Receive Stock":
            # Stage 2: Review
            st.write("### 📥 Receive Stock")
            pending = db.get_pending_shipments()
            
            if not pending:
                st.info("No pending shipments found.")
            else:
                selected_shipment = st.selectbox("Select Pending Shipment", pending)
                
                if selected_shipment:
                    items_df = db.get_shipment_items(selected_shipment)
                    
                    if not items_df.empty:
                        st.caption("Review quantities before receiving. 'In Transit' matches Excel qty. Edit 'Received' if different.")
                        st.info("💡 To delete an item (e.g. wrong upload), select the row and press 'Delete'. New items will be deleted, existing items will revert to Previous Status.")
                        
                        # Prepare for Editor
                        items_df['received_qty'] = items_df['in_transit_qty'] # Default
                        
                        edit_cfg = {
                            "in_transit_qty": st.column_config.NumberColumn("In Transit (Excel)", disabled=True),
                            "received_qty": st.column_config.NumberColumn("Qty to Receive (Edit)", min_value=0, required=True),
                            "item_no": st.column_config.TextColumn("Item No", disabled=True),
                            "item_description": st.column_config.TextColumn("Description", disabled=True),
                            "id": None
                        }
                        
                        # Show relevant cols
                        cols_to_show = ['id', 'item_no', 'item_description', 'in_transit_qty', 'received_qty', 'customer_name']
                        
                        # Store original IDs to detect deletions
                        original_ids = set(items_df['id'].tolist())
                        
                        edited_rec_df = st.data_editor(
                            items_df[cols_to_show],
                            column_config=edit_cfg,
                            use_container_width=True,
                            hide_index=True,
                            num_rows="dynamic", # Enables Add/Delete
                            key="receive_editor"
                        )
                        
                        # Detect Deletions
                        returned_ids = set(edited_rec_df['id'].dropna().tolist()) # Dropna because new rows have None ID until handled involves strict logic but here we focus on deletions
                        deleted_ids = list(original_ids - returned_ids)
                        
                        if deleted_ids:
                             if st.button(f"⚠️ Confirm Deletion of {len(deleted_ids)} Items", type="primary"):
                                 del_count, rev_count = db.remove_items_from_shipment(deleted_ids, st.session_state.get('username'))
                                 st.success(f"Processed deletions: {del_count} Deleted, {rev_count} Reverted.")
                                 time.sleep(1)
                                 st.rerun()
                        
                        # Prevent "Add" from doing anything weird (we ignore added rows effectively unless we implement logic)
                        # For now, we only care about receiving REMAINING rows.
                        
                        if st.button("✅ Confirm Receipt & Stock In", type="primary"):
                             # Filter Only Valid Rows (Existing IDs) - ignores user added empty rows if any
                             valid_rows = edited_rec_df[edited_rec_df['id'].isin(returned_ids)]
                             
                             if valid_rows.empty and not deleted_ids:
                                 st.warning("No items to receive.")
                             elif not valid_rows.empty:
                                 records_to_process = valid_rows.to_dict('records')
                                 processed_count, notifs_list = db.receive_shipment_items(records_to_process, st.session_state.get('username'))
                                 
                                 # Email Logic
                                 if notifs_list:
                                      updates_by_advisor = {}
                                      for notif in notifs_list:
                                          adv = notif['advisor']
                                          if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                                          updates_by_advisor[adv].append(notif)
                                          
                                      for adv_code, items in updates_by_advisor.items():
                                          recipients = db.get_user_emails_by_advisor_code(adv_code)
                                          for email, username in recipients:
                                              mailer.send_bulk_notification(email, items, title="Parts Received", advisor_name=username)
                                 
                                 if processed_count > 0:
                                     st.success(f"Successfully received {processed_count} items from '{selected_shipment}'. Notifications sent.")
                                     time.sleep(2)
                                     st.rerun()
                                 else:
                                     st.error("Error processing items.")

        elif mode == "3️⃣ Shipment Overview & ETA":
            st.write("### 🚢 Shipment Overview")
            
            summary_df = db.get_all_shipments_summary()
            
            if summary_df.empty:
                st.info("No shipments found.")
            else:
                # Display Summary Table
                st.dataframe(
                    summary_df,
                    column_config={
                        "shipment_ref": "Shipment Name",
                        "current_eta": "ETA",
                        "status": "Status",
                        "total_items": "Items",
                        "in_transit_count": "In Transit",
                        "received_count": "Received",
                        "last_update": "Last Updated"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                st.divider()
                st.subheader("🛠️ Manage Shipment")
                
                # Selector for Action
                ship_names = summary_df['shipment_ref'].tolist()
                sel_ship = st.selectbox("Select Shipment to Manage", ship_names)
                
                if sel_ship:
                    # Get details for selected
                    row = summary_df[summary_df['shipment_ref'] == sel_ship].iloc[0]
                    curr_status = row['status']
                    curr_eta = row['current_eta']
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.info(f"**Status:** {curr_status}")
                    with c2:
                         st.info(f"**Current ETA:** {curr_eta}")
                    
                    # Logic: If Received -> No Data View. 
                    if curr_status == 'Received':
                        st.warning("🔒 This shipment is fully received. Data view is disabled.")
                    else:
                        # In Transit -> Show Data + Edit ETA
                        st.write("#### 📅 Update ETA")
                        
                        # Handle ETA value safely
                        eta_val = datetime.now()
                        if curr_eta:
                            try:
                                eta_val = datetime.strptime(str(curr_eta), '%Y-%m-%d')
                            except:
                                pass
                                
                        new_eta_val = st.date_input("New ETA", value=eta_val)
                        
                        if st.button("Update ETA"):
                            new_eta_str = new_eta_val.strftime('%Y-%m-%d')
                            updated_items = db.update_shipment_eta(sel_ship, new_eta_str, st.session_state.get('username'))
                            
                            # Note: update_shipment_eta now returns list of updated items or empty list
                            if updated_items:
                                # Email Logic
                                updates_by_advisor = {}
                                for item in updated_items:
                                    adv = item.get('advisor')
                                    if adv and adv != 'Unknown':
                                        if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                                        updates_by_advisor[adv].append(item)
                                
                                count_emails = 0
                                for adv_code, items in updates_by_advisor.items():
                                    recipients = db.get_user_emails_by_advisor_code(adv_code)
                                    # Create human readable date for email
                                    try:
                                        nice_date = new_eta_val.strftime('%d %b %Y')
                                    except:
                                        nice_date = new_eta_str
                                        
                                    custom_msg = f"The Estimated Time of Arrival (ETA) for items in shipment '<b>{sel_ship}</b>' has been updated to <span style='color:#B12B28; font-weight:bold;'>{nice_date}</span>."
                                    
                                    for email, username in recipients:
                                        mailer.send_bulk_notification(
                                            email, 
                                            items, 
                                            title=f"ETA Update: Shipment {sel_ship}", 
                                            advisor_name=username,
                                            custom_message=custom_msg
                                        )
                                        count_emails += 1

                                st.success(f"ETA updated to {new_eta_str}. Sent notifications to {count_emails} recipients.")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Failed to update or no items affected.")
                                
                        st.divider()
                        st.write("#### 📋 Shipment Items (In Transit)")
                        # Show items
                        items_df = db.get_shipment_items(sel_ship)
                        st.dataframe(items_df)

def admin_user_management():
    # ... (No changes here, just context for tool call) 
    pass
    
def render_table_actions(df, user_types, is_admin, export_df=None):
    # ...
    # 4. Actions Area
    selected_indices = event.selection.rows
    selected_items = df.iloc[selected_indices]
    
    if not selected_items.empty:
        # ...
        # Post / Archive Action
        if can_post:
            col_post, col_info = st.columns([1, 4])
            with col_post:
                if st.button("💾 Post Selected Items", type="primary"):
                    post_count = 0
                    updates_by_advisor = {}
                    
                    for idx, row in selected_items.iterrows():
                         # ... (Permission Check / Archive Logic) ...
                         # Collect for Email
                         adv = row.get('service_advisor')
                         if adv and adv != 'Unknown':
                             if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                             updates_by_advisor[adv].append({
                                 'item_no': row.get('item_no'),
                                 'status': 'Posted / Archived',
                                 'description': row.get('item_description'),
                                 'document_no': row.get('document_no'),
                                 'customer_no': row.get('customer_no'),
                                 'customer_name': row.get('customer_name')
                             })
                             
                         post_count += 1
                    
                    # Email Logic
                    if updates_by_advisor:
                        for adv_code, items in updates_by_advisor.items():
                            emails = db.get_user_emails_by_advisor_code(adv_code)
                            for email in emails:
                                mailer.send_bulk_notification(email, items, title="Items Posted (Archived)")
                    
                    if post_count:
                        st.success(f"Posted {post_count} items. Notifications sent.")
                        time.sleep(1)
                        st.rerun()

def admin_user_management():
    # RESTRICTION: Only Super Admin (or 'sadmin') can access this
    # Check if 'super_admin' is in the type list string or is the user
    # Or specifically 'sadmin' username. But user type is better.
    current_types = st.session_state.get('user_type', '')
    if 'super_admin' not in current_types and 'sadmin' not in st.session_state.get('username', ''):
        st.warning("⚠️ Access Restricted: Only Super Admins can manage users.")
        return

    st.subheader("👤 User Management")
    
    # Create
    with st.expander("Create New User"):
        with st.form("new_user"):
            u_name = st.text_input("Username")
            u_pass = st.text_input("Password", type="password")
            # Multi-select for User Type - Renamed SADV to PRTADV
            u_types = st.multiselect("User Type", ["A", "Read Only", "ServiceADV", "PRTADV", "SaMnagment", "OTC", "admin"])
            
            # Email (New)
            u_email = st.text_input("Email Address (for notifications)")
            
            # Show Advisor Code only for Type ServiceADV? Or all can have it?
            u_code = st.selectbox("Service Advisor Code (for Type ServiceADV)", ["EMA GilbetZ", "EMB TonyR", "EMC JackS", "B&P", "OTC", "ALL", "None"], index=6)
            
            if st.form_submit_button("Create User"):
                if not u_name.strip():
                    st.error("Username cannot be blank.")
                elif 'ServiceADV' in u_types and u_code == 'None':
                    st.error("Type ServiceADV must have an Advisor Code.")
                else:
                    # u_types passed as list to db.create_user (which now handles it)
                    if db.create_user(u_name, u_pass, u_types, u_code, u_email):
                        st.success(f"User {u_name} created.")
                    else:
                        st.error("Error creating user. Username may already exist.")

    # List & Delete
    users = db.get_all_users()
    users = add_filters(users, key_suffix='users') # Add Filter
    st.dataframe(users)

    with st.expander("✏️ Edit User"):
        all_users_df = db.get_all_users()
        edit_user = st.selectbox("Select User to Edit", all_users_df['username'], key="edit_user_select")

        if edit_user:
            # Fetch current values for pre-fill
            conn_row = all_users_df[all_users_df['username'] == edit_user].iloc[0]
            current_types = [t.strip() for t in str(conn_row.get('user_type', '')).split(',') if t.strip()]
            current_code = conn_row.get('service_advisor_code', 'None') or 'None'

            with st.form("edit_user_form"):
                e_name = st.text_input("Username", value=conn_row.get('username') or '')
                e_types = st.multiselect(
                    "User Type",
                    ["A", "Read Only", "ServiceADV", "PRTADV", "SaMnagment", "OTC", "admin", "super_admin"],
                    default=[t for t in current_types if t in ["A", "Read Only", "ServiceADV", "PRTADV", "SaMnagment", "OTC", "admin", "super_admin"]]
                )
                advisor_options = ["EMA GilbetZ", "EMB TonyR", "EMC JackS", "B&P", "OTC", "ALL", "None"]
                e_code = st.selectbox(
                    "Service Advisor Code",
                    advisor_options,
                    index=advisor_options.index(current_code) if current_code in advisor_options else len(advisor_options) - 1
                )
                e_email = st.text_input("Email Address", value=conn_row.get('email') or '')
                e_pass = st.text_input("New Password (leave blank to keep current)", type="password")

                if st.form_submit_button("💾 Save Changes"):
                    success = db.update_user(
                        edit_user,
                        e_name,
                        e_types,
                        e_code,
                        e_email,
                        new_password=e_pass if e_pass else None
                    )
                    if success:
                        st.success(f"✅ User updated successfully. (Was: {edit_user}, Now: {e_name})")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Failed to update user. Does this username already exist?")

    with st.expander("Delete User"):
        del_user = st.selectbox("Select User", users['username'])
        if st.button("Delete Selected"):
            db.delete_user_by_username(del_user)
            st.success("Deleted.")
            st.rerun()


def admin_ledger_section():
    st.subheader("📖 Item Ledger & History")
    st.caption("Search to view a consolidated timeline of actions (Uploads, Updates, Posting, etc.) for matching items.")
    
    col_search, col_btn = st.columns([3, 1])
    with col_search:
        search_term = st.text_input("Search Item (Item No, Order No, or Customer)", placeholder="Enter Item No, Order, or Customer...")
    with col_btn:
        st.write("") # Spacer
        st.write("") 
        do_search = st.button("🔍 Search History", type="primary")
        
    if do_search or search_term:
        if not search_term:
            st.warning("Please enter a search term.")
            return

        # Fetch matches with permission filtering
        results = db.get_item_details(
            search_term,
            st.session_state.get('user_type', ''),
            st.session_state.get('advisor_code', '')
        )
        
        if results.empty:
            st.info("No items found matching your query.")
        else:
            # FLATTEN DATA: Create a single "Ledger" Table
            # Iterate all matches, parse their logs, and combine.
            
            all_events = []
            
            for index, row in results.iterrows():
                # Parse the log for this item
                log_df = utils.parse_log_to_df(row['updates_log'])
                
                # Calculate Aging (Days in Stock)
                aging_txt = utils.get_aging_text(
                    row.get('updates_log'), 
                    row.get('item_status'), 
                    row.get('custom_stock_date'),
                    row.get('back_order_original_date'),
                    row.get('received_date')
                )
                
                # Base Item Metadata
                item_meta = {
                    "Item No": row['item_no'],
                    "Description": row['item_description'],
                    "Order No": row['order_no'],
                    "Status": row['item_status'], # Snapshot status (current)
                    "Duration": aging_txt,
                    "Customer": row['customer_name'],
                    "Document No": row['document_no'],
                    "VIN": row['vin'],
                    "Advisor": row['service_advisor'],
                    "ETA": row['eta'],
                    "Ordered Qty": row['ordered_qty'],
                    "Received Qty": row['received_qty'],
                    "In Transit Qty": row['in_transit_qty'],
                    "Next Info": row['next_info'],
                    "Remarks": row['remarks'],
                    "Posted By": row.get('posted_by'),
                    "Posted Date": row.get('posted_at'),
                    "Back Order Date": row.get('back_order_original_date')
                }

                if not log_df.empty:
                    # Add Item Metadata to each event row
                    for _, event in log_df.iterrows():
                        event_data = item_meta.copy()
                        event_data.update({
                            "Timestamp": event['Timestamp'],
                            "Action": event['Action'],
                            "User": event['User']
                        })
                        all_events.append(event_data)
                else:
                    # Fallback for items with no log text (Legacy?)
                    event_data = item_meta.copy()
                    event_data.update({
                        "Timestamp": str(row['last_updated']),
                        "Action": "Legacy Record / No Log",
                        "User": "System"
                    })
                    all_events.append(event_data)
            
            if not all_events:
                 st.info("Items found, but no history logs available.")
            else:
                 ledger_df = pd.DataFrame(all_events)
                 
                 # Sort by Timestamp Descending
                 # Try to convert to datetime for sorting
                 ledger_df['Timestamp_dt'] = pd.to_datetime(ledger_df['Timestamp'], format='%Y-%m-%d %H:%M', errors='coerce')
                 # If parse failed (e.g. seconds included or different format), might be NaT. 
                 # Fallback sort by string if needed, but let's try.
                 ledger_df = ledger_df.sort_values(by='Timestamp_dt', ascending=False).drop(columns=['Timestamp_dt'])
                 
                 st.success(f"Found {len(results)} items with {len(ledger_df)} history events.")
                 
                 # Display Single Table with expanded columns
                 # Reorder columns for logical flow
                 cols_order = [
                     "Timestamp", "Item No", "Description", "Order No", "Action", "User", 
                     "Status", "Duration", "ETA", "Customer", "Document No", "Advisor", 
                     "Posted By", "Posted Date", "Back Order Date",
                     "VIN", "Ordered Qty", "Received Qty", "In Transit Qty", "Next Info", "Remarks"
                 ]
                 
                 # Ensure all columns exist
                 for c in cols_order:
                     if c not in ledger_df.columns:
                         ledger_df[c] = ""
                         
                 st.data_editor(
                     ledger_df[cols_order],
                     use_container_width=True,
                     hide_index=True,
                     column_config={
                         "Timestamp": st.column_config.TextColumn("Event Time", width="medium"),
                         "Item No": st.column_config.TextColumn("Item No", width="small"),
                         "Description": st.column_config.TextColumn("Description", width="medium"),
                         "Order No": st.column_config.TextColumn("Order No", width="small"),
                         "Action": st.column_config.TextColumn("Event Action", width="large"),
                         "User": st.column_config.TextColumn("User", width="small"),
                         "Status": st.column_config.TextColumn("Status", width="small"),
                         "Duration": st.column_config.TextColumn("Duration", width="small"),
                         "ETA": st.column_config.TextColumn("ETA", width="small"),
                         "Customer": st.column_config.TextColumn("Customer", width="medium"),
                         "Document No": st.column_config.TextColumn("Doc No", width="small"),
                         "Advisor": st.column_config.TextColumn("Advisor", width="small"),
                         "Posted By": st.column_config.TextColumn("Posted By", width="small"),
                         "Posted Date": st.column_config.TextColumn("Posted Date", width="medium"),
                         "Back Order Date": st.column_config.TextColumn("Back Order Date", width="medium"),
                         "VIN": st.column_config.TextColumn("VIN", width="medium"),
                         "Ordered Qty": st.column_config.NumberColumn("Ord Qty", width="small"),
                         "Received Qty": st.column_config.NumberColumn("Rec Qty", width="small"),
                         "In Transit Qty": st.column_config.NumberColumn("Transit Qty", width="small"),
                         "Next Info": st.column_config.TextColumn("Next Info", width="medium"),
                         "Remarks": st.column_config.TextColumn("Remarks", width="large"),
                     },
                     disabled=True,
                     key=f"ledger_view_{search_term}_{len(all_events)}"
                 )

# --- Main Dashboard ---
def render_header():
    """Renders the top bar with user info and logout."""
    # Container with distinct background/style could be simulated with columns
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1], vertical_alignment="center")
    
    with c1:
        st.image(str(config.ASSETS_DIR / "toppng.com-porsche-logo-black-text-png-2000x238.png"), width=400)
    
    with c2:
        st.write(f"👤 **{st.session_state['username']}**")
    
    with c3:
         info = f"Type: {st.session_state['user_type']}"
         if st.session_state.get('advisor_code'):
             info += f" | {st.session_state['advisor_code']}"
         st.caption(info)
         
    with c4:
        if st.button("Logout", use_container_width=True):
            logout()
    
    st.divider()




def main_dashboard():
    # CSS Hack for Top Padding and Hiding Toolbar
    st.markdown("""
        <style>
               /* Hide Streamlit Header/Toolbar */
               header[data-testid="stHeader"] {
                   visibility: hidden;
                   height: 0px;
               }
               /* Hide Streamlit Footer */
               footer {
                   visibility: hidden;
               }
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    margin-top: 0rem;
                }
        </style>
    """, unsafe_allow_html=True)

    # 1. Top Bar
    render_header()
    
    u_type_str = st.session_state.get('user_type', '')
    u_types = u_type_str.split(',') if u_type_str else []
    
    u_code = st.session_state['advisor_code']
    
    # IS ADMIN?
    is_admin = 'admin' in u_types or u_type_str == 'admin'
    is_super_admin = 'super_admin' in u_types or 'super_admin' in u_type_str
    
    # If Admin, show Tabs for Management
    if is_admin:
        # TABS definition
        tabs_list = ["Dashboard", "Uploads", "Users", "Posted History", "Ledger Entries"]
        if is_super_admin:
            tabs_list.insert(0, "📊 Exec Dashboard")
            
        tabs = st.tabs(tabs_list)
        
        # Index Offset if Super Admin
        idx_offset = 1 if is_super_admin else 0
        
        if is_super_admin:
            with tabs[0]:
                render_super_admin_dashboard()
        
        with tabs[0 + idx_offset]:
            # Test Data Clear Button (Temporary) - Super Admin Only
            if is_super_admin:
                c_clear, c_space = st.columns([1, 4])
                with c_clear:
                     if "confirm_clear_mgr" not in st.session_state:
                         st.session_state["confirm_clear_mgr"] = False
                         
                     if not st.session_state["confirm_clear_mgr"]:
                         if st.button("⚠️ CLEAR TABLE (Test Mode)", type="primary"):
                             st.session_state["confirm_clear_mgr"] = True
                             st.rerun()
                     else:
                         st.warning("Do you really want to clear all the data?")
                         c_yes, c_no = st.columns(2)
                         with c_yes:
                             if st.button("Yes, Clear Data", type="primary"):
                                 if db.clear_all_data():
                                     st.success("All data cleared successfully.")
                                     st.session_state["confirm_clear_mgr"] = False
                                     time.sleep(1)
                                     st.rerun()
                                 else:
                                     st.error("Failed to clear data.")
                         with c_no:
                             if st.button("Cancel"):
                                 st.session_state["confirm_clear_mgr"] = False
                                 st.rerun()
            
            show_parts_table(u_types, u_code, is_admin)
        with tabs[1 + idx_offset]:
            admin_upload_section()
        with tabs[2 + idx_offset]:
            admin_user_management()
        with tabs[3 + idx_offset]:
            st.subheader("📜 Posted / Archived Items Log")
            archived_df = db.get_archived_parts()
            
            if not archived_df.empty:
                # Add Filters
                archived_df = add_toolbar(archived_df, key_suffix='archived')
                
                if archived_df.empty:
                    st.info("No items match filter.")
                else:
                    # Add Select Column for Unship
                    archived_df_view = archived_df.copy()
                
                # Fix: Convert posted_at to datetime for Streamlit compatibility
                if 'posted_at' in archived_df_view.columns:
                    archived_df_view['posted_at'] = pd.to_datetime(archived_df_view['posted_at'], errors='coerce')

                archived_df_view.insert(0, "Select", False)
                
                # Config
                arc_cfg = {
                   "Select": st.column_config.CheckboxColumn("Select", help="Select to Unship"),
                   "id": None,
                   "posted_by": st.column_config.TextColumn("Posted By"),
                   "posted_at": st.column_config.DatetimeColumn("Posted Date", format="D MMM YYYY, HH:mm"),
                   "item_no": "Item No",
                   "item_description": "Description"
                }
                
                edited_arc_df = st.data_editor(
                    archived_df_view, 
                    column_config=arc_cfg,
                    use_container_width=True, 
                    hide_index=True,
                    key="msg_archive_editor"
                )
                
                if st.button("↩️ Unship / Restore Selected"):
                     restore_count = 0
                     # Iterate and look for selected
                     # data_editor returns the edited dataframe
                     # We filter for Select = True
                     # But data_editor with inserted column works if we check the result.
                     
                     sel_rows = edited_arc_df[edited_arc_df['Select']]
                     
                     for idx, row in sel_rows.iterrows():
                         db.restore_archived_part(row['id'], st.session_state.get('username'))
                         restore_count += 1
                         
                     if restore_count > 0:
                         st.success(f"Restored {restore_count} items to the main dashboard.")
                         time.sleep(1)
                         st.rerun()
                     else:
                         st.warning("Please select items to restore.")
            else:
                st.info("No items have been posted/archived yet.")
        
        with tabs[4 + idx_offset]:
            admin_ledger_section()

    else:
        # Normal User - Tabs View
        if 'SADV' in u_types or 'OTC' in u_types:
             # SADV/OTC also might want history, everyone does according to user request
             pass

        tab1, tab2 = st.tabs(["Dashboard", "Item History"])
        
        with tab1:
            show_parts_table(u_types, u_code, is_admin)
            
        with tab2:
            admin_ledger_section()

def add_toolbar(df, export_df=None, key_suffix='main'):
    """
    Renders a unified horizontal toolbar with Filter, Clear, Export, and Notifications.
    Returns the filtered dataframe.
    """
    if df.empty:
        return df

    filtered_df = df.copy()
    
    # Layout: 4 equal columns
    t1, t2, t3, t4 = st.columns(4, vertical_alignment="bottom")
    
    with t1:
        if hasattr(st, 'popover'):
            with st.popover("🔍 Filter Data", use_container_width=True):
                all_cols = list(df.columns)
                cols_to_filter = st.multiselect("Select Columns to Filter", all_cols, placeholder="Choose columns...")
                
                if cols_to_filter:
                    for col_name in cols_to_filter:
                        val = st.text_input(f"Filter {col_name}", key=f"filt_{col_name}_{key_suffix}")
                        if val:
                            filtered_df = filtered_df[filtered_df[col_name].astype(str).str.contains(val, case=False, na=False)]
                
                st.caption(f"Showing {len(filtered_df)} of {len(df)} rows")
                
                if st.checkbox("✅ Select All Filtered Rows", value=False, key=f"filter_select_all_{key_suffix}"):
                    st.session_state[f'select_all_filtered_{key_suffix}'] = True
                else:
                    st.session_state[f'select_all_filtered_{key_suffix}'] = False
        else:
            with st.expander("🔍 Filter Data"):
                st.warning("Streamlit is outdated. Popover not supported.")

    with t2:
        if st.button("🧹 Clear Filters", use_container_width=True, key=f"clear_filt_btn_{key_suffix}"):
             for key in list(st.session_state.keys()):
                 if key.startswith("filt_"):
                     del st.session_state[key]
             st.rerun()

    with t3:
        if export_df is not None:
             col_map = {
                 "item_no": "Item No", "item_description": "Description", "customer_name": "Customer Name",
                 "vin": "VIN", "document_no": "Document No", "service_advisor": "Service Advisor",
                 "order_no": "Order No", "item_status": "Status", "eta": "ETA", "next_info": "Next Info from PAG",
                 "ordered_qty": "Ordered Qty", "in_transit_qty": "In Transit Qty", "received_qty": "Received Qty",
                 "days_in_stock": "Duration", "cardown": "Car Down", "latest_remark": "Latest Remark"
             }
             cols_to_export = [c for c in col_map.keys() if c in export_df.columns]
             export_df_final = export_df[cols_to_export].rename(columns=col_map)
             if "Item No" in export_df_final.columns:
                 export_df_final["Item No"] = export_df_final["Item No"].astype(str)
                 
             buffer = io.BytesIO()
             with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                 export_df_final.to_excel(writer, index=False, sheet_name='Sheet1')
                 
             st.download_button(
                 label="📥 Export to Excel",
                 data=buffer.getvalue(),
                 file_name=f"parts_export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 use_container_width=True
             )
        else:
             st.button("📥 Export to Excel", disabled=True, use_container_width=True)

    with t4:
        render_notifications(as_popover=True, key_suffix=key_suffix)

    return filtered_df
    
def show_parts_table(user_types, advisor_code, is_admin):
    # Determine base view
    view_all_roles = ['A', 'Read Only', 'PRTADV', 'SADV']
    
    if is_admin:
        df = db.get_parts_view('admin')
    elif 'Read Only' in user_types:
        df = db.get_parts_view('Read Only')
    elif any(role in user_types for role in view_all_roles):
         # View all active
         df = db.get_parts_view('A') # 'A' triggers View All in DB
    elif 'SaMnagment' in user_types:
          # Group View
          df = db.get_parts_view('SaMnagment')
    elif 'OTC' in user_types:
          # OTC View (Restricted)
          df = db.get_parts_view('OTC')
    else:
        # Default / Type ServiceADV
        df = db.get_parts_view('ServiceADV', advisor_code)
    
    if df.empty:
        st.info("No records found.")
        return

    # User Filters: Hide 'Invoiced' if not admin
    if not is_admin:
        df = df[df['item_status'] != 'Invoiced']

    # Remove strict internal columns from view if desired
    if 'source_file_type' in df.columns:
        df = df.drop(columns=['source_file_type'])
        
    # --- Pre-Calculation for Export & Display ---
    # 1. Days in Stock (Needed for both)
    def calc_days(row):
        # Prefer the alias 'bo_date_fix' if available, else original
        bod = row.get('bo_date_fix')
        if not bod: bod = row.get('back_order_original_date')
        
        return utils.get_aging_text(
            row.get('updates_log'), 
            row.get('item_status'), 
            row.get('custom_stock_date'),
            bod
        )

    if 'updates_log' in df.columns:
         df['days_in_stock'] = df.apply(calc_days, axis=1)
    else:
         df['days_in_stock'] = ""

    # 2. Capture Full DataFrame for Export (Before UI Filters)
    full_export_df = df.copy()

    # 3. Apply Toolbar & Filtering
    df = add_toolbar(df, export_df=full_export_df, key_suffix='parts_main')
    
    if df.empty:
        st.info("No records match your search.")
        return

    # 4. Apply Display Formatting (Remarks Icons) - ONLY to Display DF
    def format_remark(row):
        txt = row.get('latest_remark')
        if pd.isna(txt) or not txt or str(txt).lower() == 'nan':
             return ""
        
        # Check read status
        read_at = row.get('latest_remark_read_at')
        
        # Icon Logic:
        # If unread (read_at is None) -> Blue 🔵
        # If read (read_at exists) -> Eye 👁️
        
        icon = "👁️" if read_at else "🔵"
        return f"{icon} {txt}"

    if 'latest_remark' in df.columns:
        df['latest_remark'] = df.apply(format_remark, axis=1)

    # Single Unified Table
    render_table_actions(df, user_types, is_admin, export_df=full_export_df)

# Removed render_data_view as we use a single flat table now.

def render_table_actions(df, user_types, is_admin, export_df=None):
    """
    Helper to render the data table with status coloring and actions using st.dataframe.
    """
    # Permission Check
    can_post = 'B1' in user_types or is_admin

    # --- Tools Have Been Moved to Top Toolbar ---

    # --- Days in Stock Calculation & Remarks Formatting ---
    # Moved to show_parts_table to ensure availability for export and correct separation of concerns.
    # The 'df' passed here already has 'days_in_stock' and formatted 'latest_remark'.

    # 1. Colors Setup
    def highlight_status(val):
        color = ''
        if val == 'Back Order':
            color = 'background-color: #ef5350; color: white' # Deeper Red
        elif val == 'On Order':
            color = 'background-color: #ff9800; color: black' # Orange
        elif val == 'In Transit':
             color = 'background-color: #ffe0b2; color: black' # Lighter Orange
        elif val == 'Partially Received':
            color = 'background-color: #dcedc8; color: black' # Light Green
        elif val == 'Reordered':
            color = 'background-color: #ab47bc; color: white' # Purple
        elif val == 'Received':
            color = 'background-color: #2e7d32; color: white' # Dark Green
        return color

    def highlight_days(val):
        if pd.isna(val) or val == '':
             return ''
        try:
             # Parse string like "IS 5 days" or "B.O. 10 days"
             # If just "5" (legacy), robust check
             txt = str(val)
             import re
             # Extract first number
             match = re.search(r'\d+', txt)
             if match:
                 days = int(match.group())
                 if days <= 3:
                     return 'background-color: #dcedc8; color: black' # Green
                 elif days <= 9: # 4-9
                     return 'background-color: #fff176; color: black' # Yellow
                 else: # 10+
                     return 'background-color: #ef5350; color: white' # Red
             return ''
        except:
             return ''

    # Hide internal columns from display
    cols_to_hide = ['id', 'group_key', 'latest_remark_read_at', 'shipment_ref', 'back_order_original_date', 'bo_date_fix']
    if not is_admin:
        # cols_to_hide logic for non-admin already includes back_order_original_date above if static lista
        pass
        
    display_cols = [c for c in df.columns if c not in cols_to_hide]
    df_display = df[display_cols].copy()
    
    # Apply Styler with both status and duration colors
    styler = df_display.style.map(highlight_status, subset=['item_status'])\
                              .map(highlight_days, subset=['days_in_stock'])
    
    # Permission Check
    can_post = 'PRTADV' in user_types or 'SADV' in user_types or 'OTC' in user_types or is_admin
    
    # Toggle for Bulk Selection (Controlled via Filter Expander)
    use_all_filtered = st.session_state.get('select_all_filtered_parts_main', False) and is_admin
    
    # Render styled dataframe with row selection
    selection = st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        key=f"main_parts_table_{len(df)}"
    )
    
    # Get selected row indices from dataframe selection
    if use_all_filtered:
         selected_items = df
         st.success(f"**ALL {len(df)} FILTERED ITEMS SELECTED**")
    else:
         selected_indices = selection.selection.rows if selection.selection else []
         selected_items = df.iloc[selected_indices] if selected_indices else pd.DataFrame()
    
    # 4. Actions Area
    if not selected_items.empty:
        st.divider()
        st.write(f"**Selected {len(selected_items)} items**")
        
        if is_admin:
            # --- ADMIN VIEW: Dropdown for functionalities ---
            st.subheader("⚙️ Admin Actions")
            action_choice = st.selectbox(
                "Select Action", 
                ["Choose Action...", "Post / Archive Selected", "Update ETA", "Update Backorder Date"]
            )
            
            if action_choice == "Post / Archive Selected":
                st.caption("Archive selected items (Post to History).")
                if st.button("💾 Post Selected Items", type="primary"):
                    post_count = 0
                    updates_by_advisor = {}
                    
                    for idx, row in selected_items.iterrows():
                         db.archive_part(row['id'], st.session_state.get('username', 'Unknown'))
                         
                         # Collect for Email
                         adv = row.get('service_advisor')
                         if adv and adv != 'Unknown':
                             if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                             updates_by_advisor[adv].append({
                                 'item_no': row.get('item_no'),
                                 'status': 'Posted / Archived',
                                 'description': row.get('item_description'),
                                 'document_no': row.get('document_no'),
                                 'customer_no': row.get('customer_no'),
                                 'customer_name': row.get('customer_name')
                             })
                             
                         post_count += 1
                    
                    # Email Logic
                    if updates_by_advisor:
                        for adv_code, items in updates_by_advisor.items():
                            recipients = db.get_user_emails_by_advisor_code(adv_code)
                            for email, username in recipients:
                                mailer.send_bulk_notification(email, items, title="Items Posted (Archived)", advisor_name=username)
                    
                    if post_count:
                        st.success(f"Posted {post_count} items. Notifications sent.")
                        time.sleep(1)
                        st.rerun()

            elif action_choice == "Update ETA":
                # Bulk Update Logic
                st.caption(f"Updating ETA for **{len(selected_items)}** selected items.")
                
                # Pre-fill only if 1 item
                default_eta = ""
                if len(selected_items) == 1:
                     default_eta = selected_items.iloc[0]['eta']
                
                new_eta = st.text_input("New ETA", value=default_eta, key="eta_input")
                
                if st.button("💾 Update All ETAs", type="primary"):
                    if new_eta:
                        updated_count = 0
                        for idx, row in selected_items.iterrows():
                             success, msg = db.update_eta(row['id'], new_eta, st.session_state.get('username'))
                             if success: updated_count += 1
                        
                        if updated_count > 0:
                            st.success(f"Updated ETA for {updated_count} items.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("No items updated.")
                    else:
                        st.info("Please enter an ETA.")

            elif action_choice == "Update Backorder Date":
                # Bulk Update Logic
                st.caption(f"Updating Backorder Start Date for **{len(selected_items)}** selected items.")
                
                # Pre-fill only if 1 item
                default_date = None
                if len(selected_items) == 1:
                     # Check alias then original
                     current_bod = selected_items.iloc[0].get('bo_date_fix')
                     if not current_bod: current_bod = selected_items.iloc[0].get('back_order_original_date')
                     
                     if current_bod:
                         try: default_date = pd.to_datetime(current_bod).date()
                         except: pass
                
                new_bod = st.date_input("Backorder Start Date", value=default_date, key="bod_input")
                
                if st.button("💾 Update Backorder Date", type="primary"):
                    date_str = new_bod.strftime('%Y-%m-%d') if new_bod else None
                    
                    updated_count = 0
                    for idx, row in selected_items.iterrows():
                         success, msg = db.update_back_order_date(row['id'], date_str, st.session_state.get('username'))
                         if success: updated_count += 1
                    
                    if updated_count > 0:
                        st.success(f"Backorder Date updated for {updated_count} items.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Update failed.") # Or detailed error if we tracked it
            
            # --- End Admin Actions ---
        
        else:
            # --- NON-ADMIN VIEW (PRTADV/SADV/OTC) ---
            if can_post:
                col_post, col_info = st.columns([1, 4])
                with col_post:
                    if st.button("💾 Post Selected Items", type="primary"):
                        post_count = 0
                        updates_by_advisor = {}
                        
                        for idx, row in selected_items.iterrows():
                             # PRTADV/OTC Restricted Check
                             if row.get('item_status') != 'Received':
                                 st.error(f"⚠️ Permission Denied: Only 'Received' items can be posted. (Item: {row.get('item_no')})")
                                 continue
                                 
                             db.archive_part(row['id'], st.session_state.get('username', 'Unknown'))
                             
                             # Collect for Email
                             adv = row.get('service_advisor')
                             if adv and adv != 'Unknown':
                                 if adv not in updates_by_advisor: updates_by_advisor[adv] = []
                                 updates_by_advisor[adv].append({
                                     'item_no': row.get('item_no'),
                                     'status': 'Posted / Archived',
                                     'description': row.get('item_description'),
                                     'document_no': row.get('document_no'),
                                     'customer_no': row.get('customer_no'),
                                     'customer_name': row.get('customer_name')
                                 })
                                 
                             post_count += 1
                        
                        # Email Logic
                        if updates_by_advisor:
                            for adv_code, items in updates_by_advisor.items():
                                recipients = db.get_user_emails_by_advisor_code(adv_code)
                                for email, username in recipients:
                                    mailer.send_bulk_notification(email, items, title="Items Posted (Archived)", advisor_name=username)
                        
                        if post_count:
                            st.success(f"Posted {post_count} items. Notifications sent.")
                            time.sleep(1)
                            st.rerun()
    
    # 5. Remarks Section (Show for the LAST selected item)
    st.divider()
    if not selected_items.empty:
        # Pick the last one selected as the 'Active' context for remarks
        active_item = selected_items.iloc[-1]
        render_remarks_section(active_item, is_admin)
    else:
        st.info("👆 Check the 'Select' box for a row above to view or add remarks.")
        st.subheader("📝 Remarks")
        st.caption("No item selected.")

def render_remarks_section(item_row, is_admin=False):
    st.divider()
    
    # Header with Item Info
    st.subheader(f"📝 Remarks for Item: {item_row['item_no']} - {item_row['item_description']}")
    

    
    # --- Mark as Read Action (Automatic) ---
    # Check if there is an unread remark (Blue icon logic) regarding the active item
    is_unread = item_row.get('latest_remark') and not item_row.get('latest_remark_read_at')
    
    # Auto-read Logic
    if is_unread:
         # Only trigger if the current user should "read" it? 
         # Assuming if you open it, you read it.
         count = db.mark_remarks_as_read(item_row['id'], st.session_state.get('username'))
         if count > 0:
             st.toast("✅ Remarks marked as read automatically.")
             time.sleep(0.5) 
             st.rerun()
    
    # 1. View History
    st.caption("History")
    hist_df = db.get_remarks_for_part(int(item_row['id']))
    if not hist_df.empty:
        # Specific table config
        st.dataframe(
            hist_df[['created_at', 'entered_by', 'remark_text', 'follow_up_date', 'remember_on_date']],
            column_config={
                "created_at": "Date",
                "entered_by": "User",
                "remark_text": st.column_config.TextColumn("Remark", width="large"),
                "follow_up_date": "Follow Up",
                "remember_on_date": "Remember On"
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No remarks yet.")
        
    # 2. Add New
    st.caption("Add New Remark")
    with st.form(key=f"frm_rem_{item_row['id']}"):
        new_text = st.text_area("Remark", height=100)
        c1, c2 = st.columns(2)
        with c1:
            f_date = st.date_input("Follow Up Date", value=None)
        with c2:
            r_date = st.date_input("Remember On Date (Triggers Notification)", value=None)
            
        if st.form_submit_button("Add Remark"):
            if new_text:
                db.add_remark(
                    int(item_row['id']), 
                    new_text, 
                    f_date, 
                    r_date, 
                    st.session_state.get('username')
                )
                st.success("Remark added.")
                st.rerun()
            else:
                st.warning("Please enter text.")


# --- App Entry ---
if not st.session_state['logged_in']:
    login()
else:
    # 0. Check daily reminders on load
    if 'reminders_checked' not in st.session_state:
        st.session_state['reminders_checked'] = True
        alerts = db.check_daily_reminders(st.session_state['username'])
        for a in alerts:
            st.toast(a, icon="⏰") # New streamlit toast feature is nice for this
            
    main_dashboard()
