import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# --- 2. CUSTOM UI STYLING ---
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
        color: #1e293b;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT KNOWLEDGE HUB 🏆</div>', unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION & MAPPING LOGIC ---
@st.cache_data(ttl=5)
def load_mapped_data():
    try:
        s = st.secrets["connections"]["gsheets"]
        decoded_creds = base64.b64decode(s["encoded_creds"]).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open("RCTT_Hub_DB")
        
        # Load Reference Data
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        # Load Raw Statistics
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        # Data Cleaning & Mapping (Using Lvl, CV, DC)
        stats_df['Date'] = pd.to_datetime(stats_df['Date'])
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        
        # Update numeric columns to match your spreadsheet headers
        num_cols = ['Lvl', 'CV', 'DC']
        for col in num_cols:
            if col in stats_df.columns:
                stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        return stats_df, raw_stats_ws, player_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection or Mapping Failed: {e}")
        return pd.DataFrame(), None, {}, {}

df, stats_ws, player_map, corp_map = load_mapped_data()

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    corp_df = df[df['Corp Name'] == selected_corp_name].sort_values('Date', ascending=False)
    latest_date = corp_df['Date'].max()
    latest_df = corp_df[corp_df['Date'] == latest_date]

    tab_overview, tab_leaderboards, tab_profiles, tab_admin = st.tabs([
        "🏠 Overview", "📊 Leaderboards", "👤 Member Profiles", "🔑 Admin Entry"
    ])

    # --- TAB 1: OVERVIEW ---
    with tab_overview:
        st.markdown(f'<div class="section-header">📈 {selected_corp_name} Summary ({latest_date.date()})</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Roster", f"{len(latest_df)}/20")
        m2.metric("Net Worth", f"${latest_df['CV'].sum():,.0f}M")
        m3.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}")
        m4.metric("Avg Level", f"{latest_df['Lvl'].mean():.1f}")
        
        st.write("### 🔥 Current Standings")
        st.dataframe(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], hide_index=True, use_container_width=True)

    # --- TAB 2: LEADERBOARDS & STREAKS ---
    with tab_leaderboards:
        st.markdown('<div class="section-header">🏅 Weekly Performance</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("💰 Top Company Value (CV)")
            st.dataframe(latest_df[['Player Name', 'CV']].sort_values('CV', ascending=False), hide_index=True, use_container_width=True)
        with col_b:
            st.subheader("🟢 Weekly Donation Leaders (DC)")
            st.dataframe(latest_df[['Player Name', 'DC']].sort_values('DC', ascending=False), hide_index=True, use_container_width=True)

    # --- TAB 3: MEMBER PROFILES ---
    with tab_profiles:
        st.markdown('<div class="section-header">👤 Historical Player Profile</div>', unsafe_allow_html=True)
        selected_player = st.selectbox("Select Member:", sorted(corp_df['Player Name'].unique()))
        
        p_history = corp_df[corp_df['Player Name'] == selected_player].sort_values('Date')
        
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.metric("All-Time Peak Level", p_history['Lvl'].max())
            st.metric("Lifetime Donation Vol (DC)", f"{p_history['DC'].sum():,.0f}")
            st.metric("Highest Value Hit (CV)", f"${p_history['CV'].max():,.0f}M")
        
        with c_right:
            fig = px.line(p_history, x='Date', y='CV', title='Company Value Progression', markers=True)
            st.plotly_chart(fig, use_container_width=True)

    # --- TAB 4: ADMIN ENTRY ---
    with tab_admin:
        st.markdown('<div class="section-header">🔑 Log New Entry</div>', unsafe_allow_html=True)
        with st.form("data_entry", clear_on_submit=True):
            f1, f2 = st.columns(2)
            in_date = f1.date_input("Date", date.today())
            in_uid = f1.text_input("Player UID")
            
            if in_uid in player_map:
                f1.success(f"Recognized: **{player_map[in_uid]}**")
                
            in_corp_id = f2.text_input("Corp ID", value=latest_df['Corp_ID'].iloc[0] if not latest_df.empty else "")
            in_lvl = f2.number_input("Lvl (Level)", 1, 999, 50)
            in_cv = f1.number_input("CV (Value M)", 0, 1000000, 100)
            in_dc = f2.number_input("DC (Donation Count)", 0, 100000, 0)
            
            if st.form_submit_button("Commit to Spreadsheet"):
                if in_uid and in_corp_id:
                    # Append order: Date, Corp_ID, UID, Lvl, CV, DC
                    new_row = [str(in_date), in_corp_id, in_uid, int(in_lvl), int(in_cv), int(in_dc)]
                    stats_ws.append_row(new_row)
                    st.success("Entry recorded!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("UID and Corp ID are required.")
else:
    st.info("The Hub is ready. Add data using the 'Admin Entry' tab or directly into the 'Corporation_Stats' sheet with headers: Date, Corp_ID, UID, Lvl, CV, DC.")
