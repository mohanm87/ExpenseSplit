import streamlit as st
import pandas as pd

# --- APP CONFIG ---
st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("👪 Family Expense Tally")

# --- DATA INITIALIZATION ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# Define your families and their specific members
FAMILIES = {
    "Family A": ["Dad A", "Mom A", "Kid A1"],
    "Family B": ["Dad B", "Mom B", "Kid B1", "Kid B2"],
    "Family C": ["Dad C", "Mom C"],
    "Family D": ["Person D1"],
    "Family E": ["Dad E", "Mom E", "Kid E1"]
}

# --- SIDEBAR: Session Management ---
st.sidebar.header("Settings")
session_name = st.sidebar.text_input("Occasion/Session Name", "Summer Trip 2025")

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

    # 2. If splitting by people, select specific members
    attendees_by_family = {}
    if split_type == "By Number of People" and selected_fams:
        st.write("---")
        st.write("🔍 **Select specific members present:**")
        cols = st.columns(len(selected_fams))
        for i, fam in enumerate(selected_fams):
            with cols[i]:
                attendees_by_family[fam] = st.multiselect(
                    f"{fam}", 
                    options=FAMILIES[fam], 
                    default=FAMILIES[fam]
                )

    if st.button("Add Expense"):
        if item and amount > 0 and selected_fams:
            # Logic check: if splitting by people, at least one person must be selected
            if split_type == "By Number of People":
                total_attending = sum(len(v) for v in attendees_by_family.values())
                if total_attending == 0:
                    st.error("Please select at least one person.")
                    st.stop()
            
            entry = {
                "Session": session_name,
                "Item": item,
                "Amount": amount,
                "Payer": payer_fam,
                "Split": split_type,
                "Families": selected_fams,
                "Attendees": attendees_by_family if split_type == "By Number of People" else None
            }
            st.session_state.expenses.append(entry)
            st.success(f"Added: {item}")
        else:
            st.error("Please fill all fields and select participating families.")

st.divider()

# --- CALCULATION LOGIC ---
st.header(f"📊 Summary: {session_name}")

if st.session_state.expenses:
    all_df = pd.DataFrame(st.session_state.expenses)
    df = all_df[all_df['Session'] == session_name].copy()
    
    if not df.empty:
        # Initialize Tally Dictionary
        tally = {fam: {"spent": 0.0, "owed": 0.0} for fam in FAMILIES.keys()}

        for _, row in df.iterrows():
            # Track Payer
            tally[row['Payer']]["spent"] += row['Amount']
            
            # Logic A: Equal Family Split
            if row['Split'] == "By Family (Equal)":
                share = row['Amount'] / len(row['Families'])
                for f in row['Families']:
                    tally[f]["owed"] += share
            
            # Logic B: Per Person Split (Specific Members)
            else:
                total_people_present = sum(len(members) for members in row['Attendees'].values())
                if total_people_present > 0:
                    cost_per_person = row['Amount'] / total_people_present
                    for fam, members in row['Attendees'].items():
                        tally[fam]["owed"] += cost_per_person * len(members)

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
        
        # Option to clear session
        if st.button("Delete Last Entry"):
            st.session_state.expenses.pop()
            st.rerun()
    else:
        st.info("No expenses in this session.")