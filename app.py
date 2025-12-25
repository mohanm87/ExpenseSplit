import streamlit as st
import pandas as pd
import json
import gspread
import hashlib
from google.oauth2.service_account import Credentials

# --- APP CONFIG ---
st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("👪 Family Expense Tally")

# --- DATA INITIALIZATION ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# Function to connect to Google Sheets
def get_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_client()
    try:
        return client.open("ExpenseSplit")
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ Spreadsheet Not Found!")
        st.info(f"Please share your Google Sheet named 'ExpenseSplit' with this email:\n\n`{st.secrets['gcp_service_account']['client_email']}`")
        st.stop()

def get_worksheet(sheet_name):
    sh = get_spreadsheet()
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ Occasion '{sheet_name}' not found in Google Sheets.")
        st.stop()

def get_family_sheet():
    client = get_client()
    sh = client.open("ExpenseSplit")
    try:
        return sh.worksheet("Families")
    except gspread.exceptions.WorksheetNotFound:
        # Create the sheet if it doesn't exist
        ws = sh.add_worksheet(title="Families", rows=20, cols=2)
        ws.append_row(["Family", "Count"])
        return ws

def get_visibility_sheet():
    client = get_client()
    sh = client.open("ExpenseSplit")
    try:
        return sh.worksheet("Visibility")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Visibility", rows=100, cols=2)
        ws.append_row(["Occasion", "Hidden_From"])
        return ws

def get_users_sheet():
    client = get_client()
    sh = client.open("ExpenseSplit")
    try:
        return sh.worksheet("Users")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title="Users", rows=20, cols=4)
        ws.append_row(["Username", "Password", "Role", "Family"])
        ws.append_row(["admin", make_hash("admin"), "Admin", ""]) # Default Admin
        return ws

def save_families():
    ws = get_family_sheet()
    ws.clear()
    ws.append_row(["Family", "Count"])
    rows = [[k, v] for k, v in st.session_state.families.items()]
    if rows:
        ws.append_rows(rows)

# Function to load data from sheet
def load_data(sheet_name):
    sheet = get_worksheet(sheet_name)
    try:
        data = sheet.get_all_records()
        # If sheet is empty (no headers), get_all_records might return empty or fail.
        # We need to parse the JSON strings back to lists/dicts
        parsed_data = []
        for row in data:
            # Parse 'Families' (stored as JSON string)
            if isinstance(row.get('Families'), str):
                row['Families'] = json.loads(row['Families'])
            
            # Parse 'Attendees' (stored as JSON string or empty)
            if row.get('Attendees'):
                if isinstance(row['Attendees'], str):
                    row['Attendees'] = json.loads(row['Attendees'])
            else:
                row['Attendees'] = None
            parsed_data.append(row)
        return parsed_data
    except Exception:
        return []

# Define your families and their specific members
if 'families' not in st.session_state:
    # Try loading from the "Families" sheet
    try:
        fam_sheet = get_family_sheet()
        records = fam_sheet.get_all_records()
        if records:
            st.session_state.families = {r['Family']: r['Count'] for r in records}
        else:
            raise ValueError("Empty sheet")
    except Exception:
        # Default values if sheet is empty or new
        st.session_state.families = {
            "Family A": 3, "Family B": 4, "Family C": 2, "Family D": 1, "Family E": 3
        }
        # Save these defaults to the sheet immediately
        save_families()

FAMILIES = st.session_state.families

# --- AUTHENTICATION ---
if 'user' not in st.session_state:
    st.session_state.user = None

def login():
    st.header("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            users_ws = get_users_sheet()
            users = users_ws.get_all_records()
            # Check credentials
            found_user = None
            for u in users:
                if str(u['Username']) == username and str(u['Password']) == make_hash(password):
                    found_user = u
                    break
            
            if found_user:
                st.session_state.user = found_user
                st.rerun()
            else:
                st.error("Invalid username or password")

if not st.session_state.user:
    login()
    st.stop()

# --- SIDEBAR: Session Management ---
st.sidebar.header("Occasion Manager")
st.sidebar.write(f"👤 **{st.session_state.user['Username']}** ({st.session_state.user['Role']})")
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# Change Password
with st.sidebar.expander("🔐 Change Password"):
    with st.form("change_pass_form"):
        curr_pass = st.text_input("Current Password", type="password")
        new_pass = st.text_input("New Password", type="password")
        conf_pass = st.text_input("Confirm Password", type="password")
        if st.form_submit_button("Update Password"):
            if make_hash(curr_pass) == st.session_state.user['Password']:
                if new_pass == conf_pass:
                    if new_pass:
                        try:
                            users_ws = get_users_sheet()
                            cell = users_ws.find(st.session_state.user['Username'])
                            users_ws.update_cell(cell.row, 2, make_hash(new_pass))
                            st.session_state.user['Password'] = make_hash(new_pass)
                            st.success("Password updated!")
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.error("Password cannot be empty")
                else:
                    st.error("New passwords do not match")
            else:
                st.error("Incorrect current password")

# Determine View Context
user_role = st.session_state.user['Role']
user_family = st.session_state.user['Family']

if user_role == "Admin":
    # Admin can simulate other views if needed, or just see Admin view
    view_as = st.sidebar.selectbox("View as", ["Admin"] + list(FAMILIES.keys()))
else:
    # Regular users are locked to their mapped family
    view_as = user_family

# Get list of sheets (Occasions)
sh = get_spreadsheet()
all_sheets = [ws.title for ws in sh.worksheets()]
# Exclude system sheets
occasions = [s for s in all_sheets if s not in ["Families", "Visibility", "Users"]]

# Load Visibility Rules
visibility_rules = {}
try:
    vis_ws = get_visibility_sheet()
    vis_data = vis_ws.get_all_records()
    for r in vis_data:
        if r['Occasion'] and r['Hidden_From']:
            visibility_rules[r['Occasion']] = json.loads(r['Hidden_From'])
except Exception:
    pass

# Filter Occasions based on "View As"
if view_as != "Admin":
    occasions = [occ for occ in occasions if view_as not in visibility_rules.get(occ, [])]

# If no occasions exist (e.g. only Families), default to Sheet1 or create one
if not occasions:
    occasions = ["Sheet1"]

default_ix = 0
if 'new_occasion_name' in st.session_state:
    if st.session_state.new_occasion_name in occasions:
        default_ix = occasions.index(st.session_state.new_occasion_name)
    del st.session_state.new_occasion_name

selected_occasion = st.sidebar.radio("Select Occasion", occasions, index=default_ix)
session_name = selected_occasion # Use the sheet name as the session name

# Rename Occasion (Inline)
c_ren1, c_ren2 = st.sidebar.columns([3, 1])
rename_val = c_ren1.text_input("Rename", value=selected_occasion, key=f"rename_{selected_occasion}", label_visibility="collapsed")
if c_ren2.button("💾", help="Save New Name"):
    if rename_val and rename_val != selected_occasion:
        if rename_val in all_sheets:
            st.error("Name exists!")
        else:
            try:
                ws = get_worksheet(selected_occasion)
                ws.update_title(rename_val)
                st.session_state.new_occasion_name = rename_val
                st.success("Renamed!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# Delete Occasion (Admin Only)
if user_role == "Admin":
    with st.sidebar.expander("🗑️ Delete Occasion"):
        st.warning(f"Permanently delete '{selected_occasion}'?")
        if st.button("Confirm Delete", key="del_occ_btn"):
            try:
                sh = get_spreadsheet()
                ws = get_worksheet(selected_occasion)
                sh.del_worksheet(ws)
                st.success("Deleted!")
                if 'current_occasion' in st.session_state:
                    del st.session_state.current_occasion
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# Load data for the selected occasion
# We use a session_state variable to track if we need to reload
if 'current_occasion' not in st.session_state or st.session_state.current_occasion != selected_occasion:
    st.session_state.expenses = load_data(selected_occasion)
    st.session_state.current_occasion = selected_occasion

# Add New Occasion
if user_role == "Admin":
    with st.sidebar.expander("➕ Add New Occasion"):
        new_occ_name = st.text_input("New Occasion Name")
        hide_from = st.multiselect("Hide from", list(FAMILIES.keys()))
        
        if st.button("Create Occasion"):
            if new_occ_name and new_occ_name not in all_sheets:
                try:
                    ws = sh.add_worksheet(title=new_occ_name, rows=100, cols=10)
                    ws.append_row(["Session", "Item", "Amount", "Payer", "Split", "Families", "Attendees"])
                    if hide_from:
                        v_ws = get_visibility_sheet()
                        v_ws.append_row([new_occ_name, json.dumps(hide_from)])
                    st.success(f"Created '{new_occ_name}'!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating sheet: {e}")
            elif new_occ_name in all_sheets:
                st.error("Occasion already exists.")

# --- TABS ---
if user_role == "Admin":
    tab_expenses, tab_families, tab_users = st.tabs(["💰 Expenses", "👨‍👩‍👧‍👦 Families", "👥 Users"])
else:
    tab_expenses, = st.tabs(["💰 Expenses"])
    tab_families = None
    tab_users = None

with tab_expenses:
    # --- MAIN UI: Add Expense ---
    with st.expander("➕ Add New Expense", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            item = st.text_input("Expense Item", placeholder="e.g. Dinner at Beach")
            amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
            payer_fam = st.selectbox("Who Paid?", list(FAMILIES.keys()))
            
        with col2:
            split_type = st.radio("Split Logic", ["By Family (Equal)", "By Number of People"])
            
            # 1. Select participating families first
            selected_fams = st.multiselect("Which families participated?", 
                                         list(FAMILIES.keys()), 
                                         default=list(FAMILIES.keys()))

        # 2. If splitting by people, enter count of members present
        attendees_by_family = {}
        if split_type == "By Number of People" and selected_fams:
            st.write("---")
            st.write("🔍 **Enter number of people present:**")
            cols = st.columns(len(selected_fams))
            for i, fam in enumerate(selected_fams):
                with cols[i]:
                    # Default to the total family size defined in settings
                    fam_val = FAMILIES.get(fam, 1)
                    default_count = len(fam_val) if isinstance(fam_val, list) else int(fam_val)
                    attendees_by_family[fam] = st.number_input(
                        f"{fam}", 
                        min_value=0, 
                        value=default_count,
                        step=1,
                        key=f"att_{fam}"
                    )

    if st.button("Add Expense"):
        if item and amount > 0 and selected_fams:
            # Logic check: if splitting by people, at least one person must be selected
            if split_type == "By Number of People":
                total_attending = sum(attendees_by_family.values())
                if total_attending == 0:
                    st.error("Please ensure at least one person is attending.")
                    st.stop()
            
            # Prepare row for Google Sheet
            # We use json.dumps to store lists/dicts as strings in the cells
            attendees_json = json.dumps(attendees_by_family) if split_type == "By Number of People" else ""
            families_json = json.dumps(selected_fams)
            
            row_data = [session_name, item, amount, payer_fam, split_type, families_json, attendees_json]
            
            sheet = get_worksheet(selected_occasion)
            
            # If sheet is empty, add headers first
            if len(sheet.get_all_values()) == 0:
                sheet.append_row(["Session", "Item", "Amount", "Payer", "Split", "Families", "Attendees"])
            
            sheet.append_row(row_data)
            
            st.success(f"Added: {item}")
            # Rerun to reload data from sheet
            st.rerun()
        else:
            st.error("Please fill all fields and select participating families.")

    st.divider()

    # --- CALCULATION LOGIC ---
    st.header(f"📊 Summary: {session_name}")

    if st.session_state.expenses:
        all_df = pd.DataFrame(st.session_state.expenses)
        
        # Check if the sheet has the correct headers
        required_cols = ["Session", "Item", "Amount", "Payer", "Split", "Families", "Attendees"]
        if not set(required_cols).issubset(all_df.columns):
            st.error("⚠️ Data Error: The Google Sheet is missing required headers.")
            st.info("This happens if data was added before the headers were created.")
            if st.button("🛠️ Fix Sheet (Reset & Add Headers)"):
                sheet = get_worksheet(selected_occasion)
                sheet.clear()
                sheet.append_row(required_cols)
                st.rerun()
            st.stop()

        df = all_df.copy() # The loaded data is already specific to this occasion/sheet
        
        if not df.empty:
            # Initialize Tally Dictionary
            # Merge configured families with any found in data (to handle history)
            data_families = set(df['Payer'].unique())
            for fams in df['Families']:
                if isinstance(fams, list):
                    data_families.update(fams)
            
            all_families = set(FAMILIES.keys()).union(data_families)
            tally = {fam: {"spent": 0.0, "owed": 0.0} for fam in all_families}

            for _, row in df.iterrows():
                # Track Payer
                if row['Payer'] in tally:
                    tally[row['Payer']]["spent"] += row['Amount']
                
                # Logic A: Equal Family Split
                if row['Split'] == "By Family (Equal)":
                    if row['Families']:
                        share = row['Amount'] / len(row['Families'])
                        for f in row['Families']:
                            if f in tally:
                                tally[f]["owed"] += share
                
                # Logic B: Per Person Split (Specific Members)
                else:
                    if row['Attendees']:
                        # Handle backward compatibility (list of names) vs new (count)
                        total_people_present = 0
                        counts_by_fam = {}
                        for fam, val in row['Attendees'].items():
                            c = len(val) if isinstance(val, list) else val
                            counts_by_fam[fam] = c
                            total_people_present += c
                            
                        if total_people_present > 0:
                            cost_per_person = row['Amount'] / total_people_present
                            for fam, count in counts_by_fam.items():
                                if fam in tally:
                                    tally[fam]["owed"] += cost_per_person * count

            # Build Summary Table
            summary_list = []
            for fam, values in tally.items():
                net = values["spent"] - values["owed"]
                summary_list.append({
                    "Family": fam,
                    "Total Paid ($)": round(values['spent'], 2),
                    "Share Owed ($)": round(values['owed'], 2),
                    "Balance ($)": round(net, 2),
                    "Status": "Settled" if abs(net) < 0.01 else ("To Receive" if net > 0 else "To Pay")
                })

            summary_df = pd.DataFrame(summary_list)
            st.table(summary_df)
            
            st.subheader("💸 Settlement Plan")
            
            # Display Settlement History
            settlements_df = df[df['Item'].astype(str).str.startswith("Settlement:")]
            if not settlements_df.empty:
                st.markdown("##### 📜 Settlement History")
                for index, row in settlements_df.iterrows():
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"✅ {row['Item']} - **${row['Amount']}**")
                    if c2.button("Revert", key=f"rev_{index}"):
                        sheet = get_worksheet(selected_occasion)
                        sheet.delete_rows(index + 2)  # +2 accounts for 0-based index and header row
                        st.success("Settlement reverted!")
                        st.rerun()
            
            # Logic to calculate who pays whom (Greedy Algorithm)
            debtors = []
            creditors = []
            
            for fam, values in tally.items():
                net = values["spent"] - values["owed"]
                if net < -0.01: # Negative balance means they need to pay
                    debtors.append({"fam": fam, "amount": abs(net)})
                elif net > 0.01: # Positive balance means they receive
                    creditors.append({"fam": fam, "amount": net})
            
            # Sort by amount to minimize number of transactions
            debtors.sort(key=lambda x: x['amount'], reverse=True)
            creditors.sort(key=lambda x: x['amount'], reverse=True)
            
            i, j = 0, 0
            settlements_found = False
            
            while i < len(debtors) and j < len(creditors):
                debtor = debtors[i]
                creditor = creditors[j]
                
                # The amount to settle is the minimum of what the debtor owes and the creditor needs
                amount = min(debtor['amount'], creditor['amount'])
                
                if amount > 0.01:
                    settlements_found = True
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"👉 **{debtor['fam']}** pays **{creditor['fam']}**: `${amount:.2f}`")
                    if c2.button("Mark as Paid", key=f"pay_{i}_{j}"):
                        sheet = get_worksheet(selected_occasion)
                        # Record settlement: Payer=Debtor, Split=Equal among [Creditor]
                        sheet.append_row([session_name, f"Settlement: {debtor['fam']} -> {creditor['fam']}", round(amount, 2), debtor['fam'], "By Family (Equal)", json.dumps([creditor['fam']]), ""])
                        st.success("Saved!")
                        st.rerun()
                
                # Adjust remaining amounts
                debtor['amount'] -= amount
                creditor['amount'] -= amount
                
                if debtor['amount'] < 0.01: i += 1
                if creditor['amount'] < 0.01: j += 1
                
            if not settlements_found:
                st.success("All settled up! No payments needed.")
            
            st.subheader("📝 Expense Log")
            
            # Calculate breakdown per item for the log (excluding settlements)
            log_df = df[~df['Item'].astype(str).str.startswith("Settlement:")].copy()
            for fam in FAMILIES.keys():
                log_df[fam] = 0.0
                
            for idx, row in log_df.iterrows():
                if row['Split'] == "By Family (Equal)":
                    if row['Families']:
                        share = row['Amount'] / len(row['Families'])
                        for f in row['Families']:
                            if f in FAMILIES:
                                log_df.at[idx, f] = round(share, 2)
                elif row['Attendees']:
                    total_people = 0
                    counts = {}
                    for fam, val in row['Attendees'].items():
                        c = len(val) if isinstance(val, list) else val
                        counts[fam] = c
                        total_people += c
                        
                    if total_people > 0:
                        cost_per_person = row['Amount'] / total_people
                        for fam, count in counts.items():
                            if fam in FAMILIES:
                                log_df.at[idx, fam] = round(cost_per_person * count, 2)

            # Custom table with Delete buttons
            fam_keys = list(FAMILIES.keys())
            # Define column layout: Item(2), Amount(1), Payer(1), Families...(1 each), Action(0.5)
            cols_spec = [2, 1, 1] + [1] * len(fam_keys) + [0.5]
            
            # Header
            headers = st.columns(cols_spec)
            headers[0].markdown("**Item**")
            headers[1].markdown("**Amount**")
            headers[2].markdown("**Payer**")
            for i, fam in enumerate(fam_keys):
                headers[3+i].markdown(f"**{fam}**")
            headers[-1].markdown("**Del**")
            
            # Rows
            for idx, row in log_df.iterrows():
                cols = st.columns(cols_spec)
                cols[0].write(row['Item'])
                cols[1].write(f"${row['Amount']:.2f}")
                cols[2].write(row['Payer'])
                
                # Family shares
                for i, fam in enumerate(fam_keys):
                    val = row.get(fam, 0.0)
                    if val > 0:
                        cols[3+i].write(f"${val:.2f}")
                    else:
                        cols[3+i].write("-")
                
                # Delete button
                if cols[-1].button("🗑️", key=f"del_log_{idx}"):
                    sheet = get_google_sheet()
                    sheet.delete_rows(idx + 2) # +2 for 1-based index and header
                    st.success("Deleted!")
                    st.rerun()
        else:
            st.info("No expenses in this session.")

if tab_families:
    with tab_families:
        st.header("👨‍👩‍👧‍👦 Manage Families")
        
        st.subheader("Current Families")
        for fam, count in st.session_state.families.items():
            with st.expander(fam):
                st.write(f"**Members Count:** {count}")
                if st.button(f"Remove {fam}", key=f"rem_{fam}"):
                    del st.session_state.families[fam]
                    save_families()
                    st.rerun()
        
        st.divider()
        st.subheader("Add New Family")
        new_fam_name = st.text_input("Family Name", placeholder="e.g. Family F")
        new_fam_count = st.number_input("Number of Members", min_value=1, step=1)
        
        if st.button("Add Family"):
            if new_fam_name:
                if new_fam_name in st.session_state.families:
                    st.error("Family already exists!")
                else:
                    st.session_state.families[new_fam_name] = new_fam_count
                    save_families()
                    st.success(f"Added {new_fam_name}!")
                    st.rerun()
            else:
                st.error("Please enter a name.")

if tab_users:
    with tab_users:
        st.header("👥 Manage Users")
        
        # List Users
        users_ws = get_users_sheet()
        users_data = users_ws.get_all_records()
        
        # Custom table with Delete buttons
        c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
        c1.markdown("**Username**")
        c2.markdown("**Role**")
        c3.markdown("**Family**")
        c4.markdown("**Action**")

        for i, u in enumerate(users_data):
            c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
            c1.write(str(u['Username']))
            c2.write(str(u['Role']))
            c3.write(str(u['Family']))
            
            # Prevent deleting the main admin user
            if str(u['Username']) == "admin":
                c4.write("🔒")
            else:
                if c4.button("🗑️", key=f"del_user_{i}"):
                    users_ws.delete_rows(i + 2)
                    st.success(f"Deleted {u['Username']}!")
                    st.rerun()
        
        st.divider()
        st.subheader("Add New User")
        with st.form("add_user_form"):
            u_name = st.text_input("Username")
            u_pass = st.text_input("Password", type="password")
            u_role = st.selectbox("Role", ["User", "Admin"])
            # Map to existing families
            u_fam = st.selectbox("Map to Family", [""] + list(FAMILIES.keys()))
            
            if st.form_submit_button("Create User"):
                if u_name and u_pass:
                    # Check if user exists
                    if any(str(u['Username']) == u_name for u in users_data):
                        st.error("Username already exists")
                    else:
                        users_ws.append_row([u_name, make_hash(u_pass), u_role, u_fam])
                        st.success(f"User {u_name} created!")
                        st.rerun()
                else:
                    st.error("Missing fields")