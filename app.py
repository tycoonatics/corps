import streamlit as st
import pandas as pd
from datetime import date
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

# --- 3. DATABASE CONNECTION & PROCESSING ---
@st.cache_data(ttl=5)
def load_mapped_data():
    try:
        s = st.secrets["connections"]["gsheets"]
        decoded_creds = base64.b64decode(s["encoded_creds"]).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(s["spreadsheet"])
        
        # Load Reference Data
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        status_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Status'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        # Load Stats
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        # Date Handling
        stats_df['Date'] = pd.to_datetime(stats_df['Date'], format='mixed', errors='coerce')
        stats_df = stats_df.dropna(subset=['Date'])
        
        # Mapping
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        stats_df['Status'] = stats_df['UID'].map(status_map).fillna("Inactive")
        
        # Numeric Force
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        # Calculate Weekly Gains
        stats_df = stats_df.sort_values(['UID', 'Date'])
        stats_df['Lvl Gain'] = stats_df.groupby('UID')['Lvl'].diff().fillna(0)
        stats_df['CV Gain'] = stats_df.groupby('UID')['CV'].diff().fillna(0)
        stats_df['DC Gain'] = stats_df.groupby('UID')['DC'].diff().fillna(0)
            
        return stats_df, raw_stats_ws, player_map, status_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}

df, stats_ws, player_map, status_map, corp_map = load_mapped_data()

# Helper for comma formatting in dataframes
def format_table(dataframe, columns):
    return dataframe.style.format({col: "{:,.0f}" for col in columns})

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    # FILTER: ONLY ACTIVE MEMBERS for main hub logic
    active_df = df[df['Status'].astype(str).str.contains("Active", case=False, na=False)]
    corp_df = active_df[active_df['Corp Name'] == selected_corp_name].sort_values('Date', ascending=False)
    
    if not corp_df.empty:
        latest_date = corp_df['Date'].max()
        latest_df = corp_df[corp_df['Date'] == latest_date]

        tab_overview, tab_weekly, tab_hof, tab_streaks, tab_profiles, tab_admin = st.tabs([
            "🏠 Overview", "📈 Weekly Gains", "👑 Hall of Fame", "🔥 Streaks", "👤 Member Profiles", "🔑 Admin"
        ])

        # --- TAB 1: OVERVIEW (Active Only) ---
        with tab_overview:
            st.markdown(f'<div class="section-header">📈 {selected_corp_name} Roster ({latest_date.strftime("%Y-%m-%d")})</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Active Roster", f"{len(latest_df)}")
            m2.metric("Avg Level", f"{latest_df['Lvl'].mean():,.0f}")
            m3.metric("Total Value", f"${latest_df['CV'].sum():,.0f}M")
            m4.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}")
            
            display_cols = ['Player Name', 'Lvl', 'CV', 'DC']
            st.dataframe(format_table(latest_df[display_cols], ['Lvl', 'CV', 'DC']), 
                         hide_index=True, use_container_width=True)

        # --- TAB 2: WEEKLY GAINS (Active Only) ---
        with tab_weekly:
            st.markdown('<div class="section-header">📅 Weekly Progress (Gains)</div>', unsafe_allow_html=True)
            all_weeks_dt = sorted(corp_df['Date'].unique(), reverse=True)
            week_options = [dt.strftime("%Y-%m-%d") for dt in all_weeks_dt]
            sel_week_str = st.selectbox("Select Week Starting:", options=week_options)
            sel_week_dt = pd.to_datetime(sel_week_str)
            week_data = corp_df[corp_df['Date'] == sel_week_dt]
            
            w_col1, w_col2, w_col3 = st.columns(3)
            with w_col1:
                st.subheader("📈 Lvl Gains")
                st.dataframe(format_table(week_data[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False), ['Lvl Gain']),
                             hide_index=True, use_container_width=True)
            with w_col2:
                st.subheader("💰 CV Gains (M)")
                st.dataframe(format_table(week_data[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False), ['CV Gain']),
                             hide_index=True, use_container_width=True)
            with w_col3:
                st.subheader("💫 DC Gains")
                st.dataframe(format_table(week_data[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False), ['DC Gain']),
                             hide_index=True, use_container_width=True)

        # --- TAB 3: HALL OF FAME (STRICTLY ACTIVE MEMBERS) ---
        with tab_hof:
            st.markdown('<div class="section-header">👑 All-Time Records (Currently Active Only)</div>', unsafe_allow_html=True)
            h1, h2, h3 = st.columns(3)
            
            h1.subheader("🏆 Peak Level")
            lvl_hof = corp_df.groupby('Player Name')['Lvl'].max().sort_values(ascending=False).reset_index()
            h1.dataframe(format_table(lvl_hof, ['Lvl']), hide_index=True, use_container_width=True)
            
            h2.subheader("💰 Peak CV")
            cv_hof = corp_df.groupby('Player Name')['CV'].max().sort_values(ascending=False).reset_index()
            h2.dataframe(format_table(cv_hof, ['CV']), hide_index=True, use_container_width=True)
            
            h3.subheader("💫 Lifetime DC")
            dc_hof = corp_df.groupby('Player Name')['DC'].sum().sort_values(ascending=False).reset_index()
            h3.dataframe(format_table(dc_hof, ['DC']), hide_index=True, use_container_width=True)

        # --- TAB 4: STREAKS ---
        with tab_streaks:
            st.markdown('<div class="section-header">🔥 Current Engagement Streaks</div>', unsafe_allow_html=True)
            streak_data = []
            distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
            for uid in corp_df['UID'].unique():
                p_logs = corp_df[corp_df['UID'] == uid]
                logged_dates = set(p_logs['Date'])
                count = 0
                for w in distinct_weeks:
                    if w in logged_dates: count += 1
                    else: break
                streak_data.append({"Player Name": p_logs['Player Name'].iloc[0], "Weeks Active": count})
            
            st.dataframe(format_table(pd.DataFrame(streak_data).sort_values("Weeks Active", ascending=False), ["Weeks Active"]), 
                         hide_index=True, use_container_width=True)

        # --- TAB 5: MEMBER PROFILES (ALL PROGRESSION METRICS) ---
        with tab_profiles:
            st.markdown('<div class="section-header">👤 Individual Historical Progression</div>', unsafe_allow_html=True)
            full_corp_history = df[df['Corp Name'] == selected_corp_name]
            all_players = sorted(full_corp_history['Player Name'].unique())
            sel_player = st.selectbox("Search Member:", all_players)
            p_history = full_corp_history[full_corp_history['Player Name'] == sel_player].sort_values('Date')
            
            p_col1, p_col2 = st.columns([1, 3])
            with p_col1:
                st.metric("Status", p_history['Status'].iloc[-1])
                st.metric("Peak Lvl", f"{int(p_history['Lvl'].max()):,}")
                st.metric("Max CV", f"${int(p_history['CV'].max()):,}M")
                st.metric("Lifetime DC", f"{int(p_history['DC'].sum()):,}")
            
            with p_col2:
                sub_tab1, sub_tab2, sub_tab3 = st.tabs(["📊 CV Growth", "📈 Level Growth", "💫 Donation Growth"])
                with sub_tab1:
                    st.plotly_chart(px.line(p_history, x='Date', y='CV', markers=True, title="Corporate Value Progression"), use_container_width=True)
                with sub_tab2:
                    st.plotly_chart(px.line(p_history, x='Date', y='Lvl', markers=True, title="Level Progression"), use_container_width=True)
                with sub_tab3:
                    st.plotly_chart(px.line(p_history, x='Date', y='DC', markers=True, title="Weekly Donation Record"), use_container_width=True)

        # --- TAB 6: ADMIN ---
        with tab_admin:
            st.markdown('<div class="section-header">🔑 Administration Data Entry</div>', unsafe_allow_html=True)
            pwd = st.text_input("Enter Admin Password:", type="password")
            if pwd == st.secrets.get("admin_password", "rcttaddict"):
                with st.form("admin_log", clear_on_submit=True):
                    f1, f2 = st.columns(2)
                    in_date = f1.date_input("Date (Monday)", date.today())
                    in_uid = f1.text_input("Player UID")
                    if in_uid in player_map: f1.info(f"Verified: **{player_map[in_uid]}**")
                    in_cid = f2.text_input("Corp ID", value="CORP_001")
                    in_lvl = f2.number_input("Level", 1, 999, 100)
                    in_cv = f1.number_input("CV (Millions)", 0, 1000000, 1000)
                    in_dc = f2.number_input("Donations", 0, 1000000, 0)
                    if st.form_submit_button("Commit Data"):
                        stats_ws.append_row([str(in_date), in_cid, in_uid, int(in_lvl), int(in_cv), int(in_dc)])
                        st.success("Stats Recorded!")
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.warning(f"No active members currently listed for {selected_corp_name}.")
else:
    st.info("System Ready. Please connect your spreadsheet to 'Corporation_Stats'.")
