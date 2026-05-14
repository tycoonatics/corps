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

# --- 2. CUSTOM CSS STYLING (The Awesome Look) ---
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
    /* Stealth Mode */
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
        # Use your established base64 credential decoding
        decoded_creds = base64.b64decode(s["encoded_creds"]).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open("RCTT_Hub_DB")
        
        # Load Reference Data (The Dictionary)
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        # Load Raw Statistics
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        # Data Mapping & Formatting
        stats_df['Date'] = pd.to_datetime(stats_df['Date'])
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        
        # Numeric Clean-up for headers: Lvl, CV, DC
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        return stats_df, raw_stats_ws, player_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection or Mapping Failed: {e}")
        return pd.DataFrame(), None, {}, {}

df, stats_ws, player_map, corp_map = load_mapped_data()

# --- 4. APP DASHBOARD ---
if not df.empty:
    # Sidebar Filters
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    corp_df = df[df['Corp Name'] == selected_corp_name].sort_values('Date', ascending=False)
    latest_date = corp_df['Date'].max()
    latest_df = corp_df[corp_df['Date'] == latest_date]

    # Tabs to organize all the awesome features
    tab_overview, tab_leaderboards, tab_profiles, tab_admin = st.tabs([
        "🏠 Overview", "📊 Hall of Fame", "👤 Member Profiles", "🔑 Admin Entry"
    ])

    # --- TAB 1: OVERVIEW & MONTHLY BANNERS ---
    with tab_overview:
        st.markdown(f'<div class="section-header">📈 {selected_corp_name} Stats (As of {latest_date.date()})</div>', unsafe_allow_html=True)
        
        # Monthly Gain Logic
        month_ago_date = latest_date - timedelta(days=30)
        historical_df = corp_df[corp_df['Date'] <= month_ago_date]
        
        cv_delta = 0
        dc_delta = 0
        if not historical_df.empty:
            past_date = historical_df['Date'].max()
            past_sum = corp_df[corp_df['Date'] == past_date]
            cv_delta = latest_df['CV'].sum() - past_sum['CV'].sum()
            dc_delta = latest_df['DC'].sum() - past_sum['DC'].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Roster", f"{len(latest_df)}/20")
        m2.metric("Avg Level", f"{latest_df['Lvl'].mean():.1f}")
        m3.metric("Total Value", f"${latest_df['CV'].sum():,.0f}M", delta=f"{cv_delta:+,}M Mo")
        m4.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}", delta=f"{dc_delta:+,} Mo")
        
        st.write("### 🔥 Current Week Standings")
        st.dataframe(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], hide_index=True, use_container_width=True)

    # --- TAB 2: ALL-TIME & STREAK LEADERBOARDS ---
    with tab_leaderboards:
        st.markdown('<div class="section-header">👑 Hall of Fame: All-Time Bests</div>', unsafe_allow_html=True)
        h1, h2, h3 = st.columns(3)
        with h1:
            st.subheader("🏆 Peak Level")
            st.dataframe(corp_df.groupby('Player Name')['Lvl'].max().sort_values(ascending=False), use_container_width=True)
        with h2:
            st.subheader("💰 Peak CV")
            st.dataframe(corp_df.groupby('Player Name')['CV'].max().sort_values(ascending=False), use_container_width=True)
        with h3:
            st.subheader("💫 Lifetime DC")
            st.dataframe(corp_df.groupby('Player Name')['DC'].sum().sort_values(ascending=False), use_container_width=True)

        st.markdown('<div class="section-header">🔥 Active Participation Streaks</div>', unsafe_allow_html=True)
        streak_data = []
        distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
        for uid in corp_df['UID'].unique():
            p_logs = corp_df[corp_df['UID'] == uid]
            p_name = p_logs['Player Name'].iloc[0]
            logged_dates = set(p_logs['Date'])
            count = 0
            for w in distinct_weeks:
                if w in logged_dates: count += 1
                else: break
            streak_data.append({"Player": p_name, "Streak": f"🔥 {count} Weeks"})
        st.table(pd.DataFrame(streak_data).sort_values('Streak', ascending=False).head(10))

    # --- TAB 3: MEMBER PROFILES ---
    with tab_profiles:
        st.markdown('<div class="section-header">👤 Individual Member Tracker</div>', unsafe_allow_html=True)
        sel_player = st.selectbox("Select Member:", sorted(corp_df['Player Name'].unique()))
        p_history = corp_df[corp_df['Player Name'] == sel_player].sort_values('Date')
        
        p_col1, p_col2 = st.columns([1, 2])
        with p_col1:
            st.metric("Peak Lvl", p_history['Lvl'].max())
            st.metric("Lifetime DC", f"{p_history['DC'].sum():,.0f}")
            fig_pie = px.pie(values=[p_history['DC'].sum(), corp_df['DC'].sum() - p_history['DC'].sum()], 
                             names=['Member', 'Rest of Corp'], title="Donation Contribution")
            st.plotly_chart(fig_pie, use_container_width=True)
        with p_col2:
            fig_line = px.line(p_history, x='Date', y='CV', title='CV Progression', markers=True)
            st.plotly_chart(fig_line, use_container_width=True)

    # --- TAB 4: ADMIN ENTRY ---
    with tab_admin:
        st.markdown('<div class="section-header">🔑 Log Weekly Stats</div>', unsafe_allow_html=True)
        with st.form("admin_form", clear_on_submit=True):
            f1, f2 = st.columns(2)
            in_date = f1.date_input("Log Date", date.today())
            in_uid = f1.text_input("Player UID")
            if in_uid in player_map:
                f1.success(f"Mapping to: **{player_map[in_uid]}**")
            
            in_cid = f2.text_input("Corp ID", value=latest_df['Corp_ID'].iloc[0] if not latest_df.empty else "")
            in_lvl = f2.number_input("Lvl", 1, 999, 50)
            in_cv = f1.number_input("CV (M)", 0, 1000000, 100)
            in_dc = f2.number_input("DC", 0, 100000, 0)
            
            if st.form_submit_button("Commit Data"):
                if in_uid and in_cid:
                    new_row = [str(in_date), in_cid, in_uid, int(in_lvl), int(in_cv), int(in_dc)]
                    stats_ws.append_row(new_row)
                    st.success("Entry Saved!")
                    st.cache_data.clear()
                    st.rerun()
else:
    st.info("Hub ready. Please ensure your 'Reference_Data' and 'Corporation_Stats' sheets are populated.")
