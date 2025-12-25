import streamlit as st
import pandas as pd

# --- APP CONFIG ---
st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("👪 Family Expense Tally")

# --- DATA INITIALIZATION (In-Memory for now) ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# Mock Data for Families
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
        # Multi-select for participating families
        participants = st.multiselect("Which families participated?", 
                                     list(FAMILIES.keys()), 
                                     default=list(FAMILIES.keys()))

    if st.button("Add Expense"):
        if item and amount > 0 and participants:
            entry = {
                "Session": session_name,
                "Item": item,
                "Amount": amount,
                "Payer": payer_fam,
                "Split": split_type,
                "Participants": participants
            }
            st.session_state.expenses.append(entry)
            st.success("Expense Added!")
        else:
            st.error("Please fill all fields.")

---

# --- CALCULATION LOGIC ---
st.header(f"📊 Summary: {session_name}")

if st.session_state.expenses:
    df = pd.DataFrame(st.session_state.expenses)
    df = df[df['Session'] == session_name] # Filter by current session
    
    st.subheader("Transaction Log")
    st.dataframe(df, use_container_width=True)

    # Initialize Tally Dictionary
    # {FamilyName: [Total Spent, Total Owed]}
    tally = {fam: {"spent": 0.0, "owed": 0.0} for fam in FAMILIES.keys()}

    for _, row in df.iterrows():
        # 1. Track who spent money
        tally[row['Payer']]["spent"] += row['Amount']
        
        # 2. Track who owes money based on logic
        if row['Split'] == "By Family (Equal)":
            share = row['Amount'] / len(row['Participants'])
            for f in row['Participants']:
                tally[f]["owed"] += share
                
        else: # By Number of People
            # Calculate total people across all participating families
            total_people = sum([len(FAMILIES[f]) for f in row['Participants']])
            if total_people > 0:
                cost_per_person = row['Amount'] / total_people
                for f in row['Participants']:
                    family_share = cost_per_person * len(FAMILIES[f])
                    tally[f]["owed"] += family_share

    # --- FINAL TALLY TABLE ---
    summary_data = []
    for fam, values in tally.items():
        net = values["spent"] - values["owed"]
        summary_data.append({
            "Family": fam,
            "Total Paid": f"${values['spent']:.2f}",
            "Share Owed": f"${values['owed']:.2f}",
            "Balance": f"${net:.2f}",
            "Status": "Settled" if net == 0 else ("To Receive" if net > 0 else "To Pay")
        })

    st.subheader("Final Balances")
    st.table(pd.DataFrame(summary_data))
else:
    st.info("No expenses added yet for this session.")