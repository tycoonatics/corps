import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from datetime import date

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# --- 2. CUSTOM UI STYLING (Knowledge Hub Aesthetic) ---
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-family: 'Arial Black', sans-serif;
        font-size: 3rem;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border: 1px solid #d1d5db;
        padding: 15px;
        border-radius: 10px;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1e293b;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 2px solid #ff0080;
        padding-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT KNOWLEDGE HUB 🏆</div>', unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION (Base64 Security) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        s = st.secrets["connections"]["gsheets"]
        decoded_creds = base64.b64decode(s["encoded_creds"]).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open_by_url(s["spreadsheet"])
        worksheet = sh.worksheet("Corporation_Stats")
        
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None

# --- 4. DATA PROCESSING ---
df, worksheet = load_data()

if not df.empty:
    # Ensure proper data types exactly like offline version
    df['Date'] = pd.to_datetime(df['Date'])
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0)
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(1)

    # --- 5. SIDEBAR (STAYS THE SAME) ---
    st.sidebar.header("Navigation")
    corps = sorted(df['Corp Name'].unique())
    selected_corp = st.sidebar.selectbox("Choose Corporation", corps)
    
    # Filter for selected corp and most recent update date
    corp_data = df[df['Corp Name'] == selected_corp]
    latest_date = corp_data['Date'].max()
    latest_stats = corp_data[corp_data['Date'] == latest_date]

    # --- 6. TOP LEVEL METRICS (Offline Version Layout) ---
    st.markdown(f'<div class="section-header">📈 {selected_corp} Overview (As of {latest_date.date()})</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Members", len(latest_stats))
    m2.metric("Total Net Worth", f"${latest_stats['Company Value'].sum():,.0f}M")
    m3.metric("Total Donations", f"{latest_stats['Donation Count'].sum():,.0f}")
    avg_lvl = latest_stats['Player Level'].mean()
    m4.metric("Average Level", f"{avg_lvl:.1f}")

    # --- 7. LEADERBOARDS (Offline Version Layout) ---
    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.write("### 💰 Top Company Value")
        top_val = latest_stats[['Player Name', 'Company Value']].sort_values(by='Company Value', ascending=False).head(10)
        st.dataframe(top_val, use_container_width=True, hide_index=True)

    with col_right:
        st.write("### 🟢 Top Donators")
        top_don = latest_stats[['Player Name', 'Donation Count']].sort_values(by='Donation Count', ascending=False).head(10)
        st.dataframe(top_don, use_container_width=True, hide_index=True)

    # --- 8. ADMIN ENTRY FORM (Offline Version Functionality) ---
    st.divider()
    with st.expander("🛠️ Admin: Add/Update Member Stats"):
        with st.form("admin_form", clear_on_submit=True):
            st.write("Submit stats for a player. This will add a new row to the database.")
            c1, c2, c3 = st.columns(3)
            f_date = c1.date_input("Report Date", date.today())
            f_corp = c1.selectbox("Corporation", corps)
            f_name = c2.text_input("Player Name")
            f_lvl = c2.number_input("Player Level", 1, 999, 50)
            f_val = c3.number_input("Company Value (Millions)", 0, 1000000, 100)
            f_don = c3.number_input("Donation Count", 0, 100000, 0)
            
            if st.form_submit_button("Submit Stats to Google Sheets"):
                if f_name:
                    try:
                        new_row = [str(f_date), f_corp, f_name, f_lvl, f_val, f_don]
                        worksheet.append_row(new_row)
                        st.success(f"Successfully logged stats for {f_name}!")
                        st.cache_data.clear() # Forces app to reload fresh data
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error submitting data: {e}")
                else:
                    st.warning("Please enter a player name before submitting.")

else:
    st.warning("⚠️ No data found. Please check your 'Secrets' configuration and ensure the Spreadsheet has data in 'Corporation_Stats'.")
