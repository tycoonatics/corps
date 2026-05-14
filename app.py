import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from datetime import date

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# --- 2. VIBRANT CUSTOM STYLING (Celebration Corner Aesthetic) ---
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
        background-color: #ffffff;
        border-left: 5px solid #ff0080;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .section-banner {
        background-color: #1e293b;
        color: #00f2ff;
        padding: 10px 20px;
        border-radius: 8px;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT KNOWLEDGE HUB 🏆</div>', unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION ---
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

# --- 4. DATA PROCESSING & DASHBOARD ---
df, worksheet = load_data()

if not df.empty:
    # Data Normalization
    df['Date'] = pd.to_datetime(df['Date'])
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0)
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(1)

    # Sidebar Navigation
    st.sidebar.markdown("### 🎮 GAME CENTER")
    corps = sorted(df['Corp Name'].unique())
    selected_corp = st.sidebar.selectbox("Select Corporation", corps)
    
    corp_data = df[df['Corp Name'] == selected_corp]
    latest_date = corp_data['Date'].max()
    latest_stats = corp_data[corp_data['Date'] == latest_date]

    # --- TOP METRICS ---
    st.markdown(f'<div class="section-banner">📊 {selected_corp} LIVE STATS</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Members", len(latest_stats))
    m2.metric("Corp Net Worth", f"${latest_stats['Company Value'].sum():,.0f}M")
    m3.metric("Weekly Donations", f"{latest_stats['Donation Count'].sum():,.0f}")
    m4.metric("Avg Player Level", f"{latest_stats['Player Level'].mean():.1f}")

    # --- LEADERBOARDS (Celebration Corner View) ---
    st.markdown('<div class="section-banner">🌟 TOP PERFORMERS 🌟</div>', unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.write("### 💰 Value Leaders")
        top_val = latest_stats[['Player Name', 'Company Value']].sort_values(by='Company Value', ascending=False).head(10)
        st.dataframe(top_val, use_container_width=True, hide_index=True)

    with col_r:
        st.write("### 🟢 Donation Kings")
        top_don = latest_stats[['Player Name', 'Donation Count']].sort_values(by='Donation Count', ascending=False).head(10)
        st.dataframe(top_don, use_container_width=True, hide_index=True)

    # --- ADMIN ENTRY (Teddies Challenge / MPG Style) ---
    st.markdown('<div class="section-banner">🛠️ ADMIN: LOG PLAYER PROGRESS</div>', unsafe_allow_html=True)
    with st.expander("Click to Open Admin Console"):
        with st.form("admin_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            f_date = c1.date_input("Log Date", date.today())
            f_corp = c1.selectbox("Corp", corps)
            f_name = c2.text_input("Player Name")
            f_lvl = c2.number_input("Level", 1, 999, 50)
            f_val = c3.number_input("Value (M)", 0, 1000000, 100)
            f_don = c3.number_input("Donations", 0, 100000, 0)
            
            if st.form_submit_button("SAVE TO CLOUD"):
                if f_name:
                    new_row = [str(f_date), f_corp, f_name, f_lvl, f_val, f_don]
                    worksheet.append_row(new_row)
                    st.success(f"Successfully logged {f_name}!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning("Player Name is required.")

else:
    st.warning("⚠️ No data found. Please ensure your Spreadsheet is correctly shared.")
