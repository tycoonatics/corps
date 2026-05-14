import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# 1. Page Configuration
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# Custom CSS for better UI
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px 15px;
        border-radius: 6px;
    }
    .section-header {
        background-color: #e2e8f0;
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: bold;
        margin-bottom: 10px;
        margin-top: 25px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 RCTT Corporation Hub Network")

# 2. Database Connection Function
@st.cache_data(ttl=10)
def load_data_from_sheets():
    try:
        s = st.secrets["connections"]["gsheets"]
        
        # Using the exact keys from your TOML
        creds_dict = {
            "type": s["type"],
            "project_id": s["project_id"],
            "private_key_id": s["private_key_id"],
            "private_key": s["private_key"],
            "client_email": s["client_email"],
            "client_id": s["client_id"],
            "auth_uri": s["auth_uri"],
            "token_uri": s["token_uri"],
            "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
            "client_x509_cert_url": s["client_x509_cert_url"]
        }
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open the specific worksheet
        workbook = client.open_by_url(s["spreadsheet"])
        worksheet = workbook.worksheet("Corporation_Stats")
        
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame(), None

# 3. Load Data
df, target_worksheet = load_data_from_sheets()

if not df.empty:
    # Convert types for calculation
    df['Date'] = pd.to_datetime(df['Date'])
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(0)
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0)

    # 4. Top Navigation & Filters
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp = st.selectbox("Select Corporation View:", available_corps)
    
    # Filter data for selected corp and latest date
    corp_df = df[df['Corp Name'] == selected_corp]
    latest_date = corp_df['Date'].max()
    latest_df = corp_df[corp_df['Date'] == latest_date]

    # 5. Dashboard Metrics
    st.markdown('<div class="section-header">📈 Live Stats Summary</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Corp", selected_corp)
    m2.metric("Members", len(latest_df))
    m3.metric("Total Value", f"${latest_df['Company Value'].sum():,.0f} M")
    m4.metric("Weekly Donations", f"{latest_df['Donation Count'].sum():,.0f}")

    # 6. Leaderboards
    st.markdown('<div class="section-header">📊 Leaderboards (Latest Update)</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("💰 Top Company Value")
        val_leader = latest_df[["Player Name", "Company Value"]].sort_values("Company Value", ascending=False)
        st.dataframe(val_leader, use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("🟢 Top Donators")
        don_leader = latest_df[["Player Name", "Donation Count"]].sort_values("Donation Count", ascending=False)
        st.dataframe(don_leader, use_container_width=True, hide_index=True)

    # 7. Admin Data Entry
    st.markdown('<div class="section-header">🔑 Admin: Update Member Stats</div>', unsafe_allow_html=True)
    with st.form("data_entry", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        new_date = f1.date_input("Update Date", date.today())
        new_corp = f1.selectbox("Target Corp", available_corps)
        new_name = f2.text_input("Player Name")
        new_lvl = f2.number_input("Player Level", 1, 150, 50)
        new_val = f3.number_input("Company Value", 0, 2000000000, 1000000)
        new_don = f3.number_input("Donation Count", 0, 10000, 0)
        
        submit = st.form_submit_button("Submit Update to Cloud")
        
        if submit:
            if new_name:
                try:
                    target_worksheet.append_row([str(new_date), new_corp, new_name, new_lvl, new_val, new_don])
                    st.success(f"Successfully updated stats for {new_name}!")
                    st.cache_data.clear() # Refresh data immediately
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to write to Sheet: {e}")
            else:
                st.warning("Please enter a Player Name.")

else:
    st.warning("Database empty or connection pending. Ensure the Service Account has 'Editor' access to the Google Sheet.")
