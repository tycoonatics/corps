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

# 1. Robust Google Sheets Connection
@st.cache_data(ttl=5)
def load_data_from_sheets():
    try:
        # Load credentials and force them into a clean dictionary
        creds_info = {
            "type": st.secrets["connections"]["gsheets"]["type"],
            "project_id": st.secrets["connections"]["gsheets"]["project_id"],
            "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
            "private_key": st.secrets["connections"]["gsheets"]["private_key"],
            "client_email": st.secrets["connections"]["gsheets"]["client_email"],
            "client_id": st.secrets["connections"]["gsheets"]["client_id"],
            "auth_uri": st.secrets["connections"]["gsheets"]["auth_uri"],
            "token_uri": st.secrets["connections"]["gsheets"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["connections"]["gsheets"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"]
        }
        
        # CLEANUP: Fix padding and PEM formatting errors
        # This replaces literal "\n" strings with actual newlines and strips trailing whitespace
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        # Authenticate
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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

    # Sidebar/Top Selection
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp = st.selectbox("Choose Active Corporation:", available_corps)
    corp_df = df[df['Corp Name'] == selected_corp]
    
    if not corp_df.empty:
        latest_date = corp_df['Date'].max()
        latest_df = corp_df[corp_df['Date'] == latest_date]
        
        # METRICS ROW
        total_value = latest_df['Company Value'].sum()
        total_donations = latest_df['Donation Count'].sum()
        member_count = latest_df['Player Name'].nunique()
        
        # Monthly Delta Logic
        month_ago_date = latest_date - timedelta(days=30)
        hist_df = corp_df[corp_df['Date'] <= month_ago_date]
        
        cv_delta, dc_delta = 0, 0
        if not hist_df.empty:
            oldest_date = hist_df['Date'].max()
            past_df = corp_df[corp_df['Date'] == oldest_date]
            cv_delta = total_value - past_df['Company Value'].sum()
            dc_delta = total_donations - past_df['Donation Count'].sum()
            
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Active Corp", selected_corp)
        m_col2.metric("Roster", f"{member_count}/20")
        m_col3.metric("Total Value", f"${total_value:,.0f} M", delta=f"{cv_delta:+,} M")
        m_col4.metric("Weekly Donations", f"{total_donations:,} DC", delta=f"{dc_delta:+,} DC")
        
        # WEEKLY LEADERBOARDS
        st.markdown('<div class="section-header">📊 Weekly Performance</div>', unsafe_allow_html=True)
        l1, l2, l3 = st.columns(3)
        with l1:
            st.subheader("🔺 Levels")
            st.dataframe(latest_df[["Player Name", "Player Level"]].sort_values("Player Level", ascending=False), use_container_width=True)
        with l2:
            st.subheader("💰 Company Value")
            st.dataframe(latest_df[["Player Name", "Company Value"]].sort_values("Company Value", ascending=False), use_container_width=True)
        with l3:
            st.subheader("🟢 Donations")
            st.dataframe(latest_df[["Player Name", "Donation Count"]].sort_values("Donation Count", ascending=False), use_container_width=True)

        # STREAKS
        st.markdown('<div class="section-header">🔥 Active Streaks</div>', unsafe_allow_html=True)
        streak_data = []
        distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
        for player in corp_df['Player Name'].unique():
            p_logs = corp_df[corp_df['Player Name'] == player]
            dates = set(p_logs['Date'])
            w_streak = 0
            for w in distinct_weeks:
                if w in dates: w_streak += 1
                else: break
            streak_data.append({"Player": player, "Streak": f"🔥 {w_streak} Weeks"})
        st.dataframe(pd.DataFrame(streak_data).sort_values("Streak", ascending=False), use_container_width=True)

        # ADMIN FORM
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
                    st.error("Missing Fields")
else:
    st.warning("Database empty or connection pending.")
