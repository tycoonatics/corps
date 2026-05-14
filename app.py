import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import json
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# --- 2. CUSTOM CSS STYLING ---
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-family: 'Arial Black', sans-serif;
        font-size: 2.5rem;
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

# --- 3. DATABASE CONNECTION ---
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
        
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        stats_df['Date'] = pd.to_datetime(stats_df['Date'])
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        
        for col in ['Lvl', 'CV', 'DC']:
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

    tab_overview, tab_leaderboards, tab_streaks, tab_profiles, tab_admin = st.tabs([
        "🏠 Overview", "📊 Hall of Fame", "🔥 Streaks", "👤 Member Profiles", "🔑 Admin Entry"
    ])

    with tab_overview:
        st.markdown(f'<div class="section-header">📈 {selected_corp_name} Stats ({latest_date.date()})</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Roster", f"{len(latest_df)}/20")
        m2.metric("Avg Level", f"{latest_df['Lvl'].mean():.1f}")
        m3.metric("Total Value", f"${latest_df['CV'].sum():,.0f}M")
        m4.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}")
        st.dataframe(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], hide_index=True, use_container_width=True)

    with tab_leaderboards:
        st.markdown('<div class="section-header">👑 Hall of Fame: All-Time Bests</div>', unsafe_allow_html=True)
        h1, h2, h3 = st.columns(3)
        h1.subheader("🏆 Peak Level")
        h1.dataframe(corp_df.groupby('Player Name')['Lvl'].max().sort_values(ascending=False), use_container_width=True)
        h2.subheader("💰 Peak CV")
        h2.dataframe(corp_df.groupby('Player Name')['CV'].max().sort_values(ascending=False), use_container_width=True)
        h3.subheader("💫 Lifetime DC")
        h3.dataframe(corp_df.groupby('Player Name')['DC'].sum().sort_values(ascending=False), use_container_width=True)

    with tab_streaks:
        st.markdown('<div class="section-header">🔥 Corporation Engagement Streaks</div>', unsafe_allow_html=True)
        streak_data = []
        distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
        for uid in corp_df['UID'].unique():
            p_logs = corp_df[corp_df['UID'] == uid]; p_name = p_logs['Player Name'].iloc[0]
            logged_dates = set(p_logs['Date'])
            act_streak = 0
            for w in distinct_weeks:
                if w in logged_dates: act_streak += 1
                else: break
            don_streak = 0
            for w in distinct_weeks:
                if w in logged_dates:
                    if p_logs[p_logs['Date'] == w]['DC'].values[0] > 0: don_streak += 1
                    else: break
                else: break
            streak_data.append({"Player Name": p_name, "Activity Streak": act_streak, "Donation Streak": don_streak})
        st.dataframe(pd.DataFrame(streak_data).sort_values(by="Activity Streak", ascending=False), hide_index=True, use_container_width=True)

    with tab_profiles:
        st.markdown('<div class="section-header">👤 Individual Member Tracker</div>', unsafe_allow_html=True)
        sel_player = st.selectbox("Select Member:", sorted(corp_df['Player Name'].unique()))
        p_history = corp_df[corp_df['Player Name'] == sel_player].sort_values('Date')
        p_col1, p_col2 = st.columns([1, 2])
        p_col1.metric("Peak Lvl", p_history['Lvl'].max())
        p_col1.metric("Lifetime DC", f"{p_history['DC'].sum():,.0f}")
        p_col2.plotly_chart(px.line(p_history, x='Date', y='CV', title='CV Progression', markers=True), use_container_width=True)

    # --- TAB 5: SECURE ADMIN ENTRY ---
    with tab_admin:
        st.markdown('<div class="section-header">🔑 Administration Access</div>', unsafe_allow_html=True)
        
        # 1. Ask for Password First
        admin_key_input = st.text_input("Enter Admin Password to Unlock Form:", type="password")
        
        # 2. Check Password against Secrets
        # Defaulting to "RCTT2024" if you haven't set a secret yet
        correct_password = st.secrets.get("admin_password", "RCTT2024")
        
        if admin_key_input == correct_password:
            st.success("Access Granted. You may now log statistics.")
            with st.form("admin_form", clear_on_submit=True):
                f1, f2 = st.columns(2)
                in_date = f1.date_input("Log Date", date.today())
                in_uid = f1.text_input("Player UID")
                if in_uid in player_map: f1.info(f"Verified: **{player_map[in_uid]}**")
                
                in_cid = f2.text_input("Corp ID", value=latest_df['Corp_ID'].iloc[0] if not latest_df.empty else "")
                in_lvl = f2.number_input("Lvl", 1, 999, 50)
                in_cv = f1.number_input("CV (M)", 0, 1000000, 100)
                in_dc = f2.number_input("DC", 0, 100000, 0)
                
                if st.form_submit_button("Commit Data"):
                    if in_uid and in_cid:
                        stats_ws.append_row([str(in_date), in_cid, in_uid, int(in_lvl), int(in_cv), int(in_dc)])
                        st.success("Entry Saved!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Missing UID or Corp ID.")
        elif admin_key_input != "":
            st.error("Invalid Password. Access Denied.")

else:
    st.info("Hub ready. Please ensure your 'Reference_Data' and 'Corporation_Stats' sheets are populated.")
