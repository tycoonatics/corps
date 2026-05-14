import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Set up widescreen page layout
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# Custom CSS styling
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

# 1. Connect to Google Sheets with Robust Key Cleaning
@st.cache_data(ttl=5)
def load_data_from_sheets():
    try:
        # Fetch raw secrets
        s = st.secrets["connections"]["gsheets"]
        
        # CLEAN KEY: Replace escaped newlines, strip spaces, and normalize
        raw_key = s["private_key"]
        clean_key = raw_key.replace("\\n", "\n").strip()
        
        creds_info = {
            "type": s["type"],
            "project_id": s["project_id"],
            "private_key_id": s["private_key_id"],
            "private_key": clean_key,
            "client_email": s["client_email"],
            "client_id": s["client_id"],
            "auth_uri": s["auth_uri"],
            "token_uri": s["token_uri"],
            "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
            "client_x509_cert_url": s["client_x509_cert_url"]
        }
        
        sheet_url = s["spreadsheet"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Authenticate
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open Worksheet
        workbook = client.open_by_url(sheet_url)
        worksheet = workbook.worksheet("Corporation_Stats")
        records = worksheet.get_all_records()
        
        return pd.DataFrame(records), worksheet, sheet_url
    except Exception as e:
        st.error(f"API Authentication Failed: {e}")
        return pd.DataFrame(), None, None

# Initialize Data
df, target_worksheet, active_sheet_url = load_data_from_sheets()

if not df.empty:
    # Data Cleaning
    df['Date'] = pd.to_datetime(df['Date'])
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(0).astype(int)
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0).astype(int)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0).astype(int)

    # UI Selection
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp = st.selectbox("Choose Active Corporation:", available_corps)
    corp_df = df[df['Corp Name'] == selected_corp]
    
    if not corp_df.empty:
        latest_date = corp_df['Date'].max()
        latest_df = corp_df[corp_df['Date'] == latest_date]
        
        # Metrics Row
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Active Corp", selected_corp)
        m_col2.metric("Roster", f"{latest_df['Player Name'].nunique()}/20")
        m_col3.metric("Total Value", f"${latest_df['Company Value'].sum():,.0f} M")
        m_col4.metric("Weekly Donations", f"{latest_df['Donation Count'].sum():,} DC")
        
        # Weekly Performance Table
        st.markdown('<div class="section-header">📊 Weekly Performance Leaderboards</div>', unsafe_allow_html=True)
        st.dataframe(latest_df[["Player Name", "Player Level", "Company Value", "Donation Count"]].sort_values("Company Value", ascending=False), use_container_width=True)

        # Admin Log Panel
        st.markdown('<div class="section-header">🔑 Admin Log Panel</div>', unsafe_allow_html=True)
        with st.form("entry_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            i_date = f1.date_input("Date", date.today())
            i_corp = f1.text_input("Corp", value=selected_corp)
            i_name = f2.text_input("Player Name")
            i_lvl = f2.number_input("Level", 1, 150, 50)
            i_val = f3.number_input("Value", 0, 999999999, 1000000)
            i_don = f3.number_input("Donations", 0, 10000, 0)
            
            if st.form_submit_button("Submit Stats"):
                if i_name and i_corp:
                    target_worksheet.append_row([str(i_date), i_corp, i_name, i_lvl, i_val, i_don])
                    st.success(f"Logged {i_name}!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Fields cannot be empty.")
else:
    st.warning("Database empty or connection pending.")
