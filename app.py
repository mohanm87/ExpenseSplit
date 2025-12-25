import streamlit as st
import pandas as pd

# --- APP CONFIG ---
st.set_page_config(page_title="Family Expense Tracker", layout="wide")
st.title("👪 Family Expense Tally")

# --- DATA INITIALIZATION ---
if 'expenses' not in st.session_state:
    st.session_state.expenses = []

# Mock Data for Families (You can edit these names/counts)
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
            st.success(f"Added: {item}")
        else:
            st.error("Please fill all fields.")

# Visual separator (Fixed the syntax error here)
st.divider()

# --- CALCULATION LOGIC ---
st.header(f"📊 Summary: {session_name}")

if st.session_state.expenses:
    # Convert session state to DataFrame
    all_df = pd.DataFrame(st.session_state.expenses)
    # Filter by current session
    df = all_df[all_df['Session'] == session_name].copy()
    
    if not df.empty:
        st.subheader("Transaction Log")
        st.dataframe(df, use_container_width=True)

        # Initialize Tally Dictionary
        tally = {fam: {"spent": 0.0, "owed": 0.0} for fam in FAMILIES.keys()}

        for _, row in df.iterrows():
            # 1. Track who spent money
            tally[row['Payer']]["spent"] += row['Amount']
            
            # 2. Track who owes money based on logic
            if row['Split'] == "By Family (Equal)":
                share = row['Amount'] / len(row['Participants'])
                for f in row['Participants']:
                    tally[f]["owed"] += share
            else: 
                # Split By Number of People
                total_people = sum([len(FAMILIES[f]) for f in row['Participants']])
                if total_people > 0:
                    cost_per_person = row['Amount'] / total_people
                    for f in row['Participants']:
                        family_share = cost_per_person * len(FAMILIES[f])
                        tally[f]["owed"] += family_share

        # --- FINAL TALLY TABLE ---
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
        st.subheader("Final Balances")
        st.table(summary_df)

        # Download Button
        csv = summary_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Tally as CSV", csv, f"{session_name}_tally.csv", "text/csv")
    else:
        st.info(f"No expenses found for session: {session_name}")
else:
    st.info("Start by adding an expense above.")