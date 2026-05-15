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

# --- 2. CSS STYLING (Dark Mode Friendly) ---
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-family: 'Arial Black', sans-serif;
        font-size: 2rem;
        margin-bottom: 30px;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 15px;
        border-radius: 10px;
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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT KNOWLEDGE HUB </div>', unsafe_allow_html=True)

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
        
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        status_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Status'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        stats_df['Date'] = pd.to_datetime(stats_df['Date'], format='mixed', errors='coerce')
        stats_df = stats_df.dropna(subset=['Date'])
        
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        stats_df['Status'] = stats_df['UID'].map(status_map).fillna("Inactive")
        
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        stats_df = stats_df.sort_values(['UID', 'Date'])
        stats_df['Lvl Gain'] = stats_df.groupby('UID')['Lvl'].diff().fillna(0)
        stats_df['CV Gain'] = stats_df.groupby('UID')['CV'].diff().fillna(0)
        stats_df['DC Gain'] = stats_df.groupby('UID')['DC'].diff().fillna(0)
            
        return stats_df, raw_stats_ws, player_map, status_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}

df, stats_ws, player_map, status_map, corp_map = load_mapped_data()

def format_table(dataframe, columns):
    return dataframe.style.format({col: "{:,.0f}" for col in columns})

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    # Pre-filtering for the current corporation
    full_corp_history = df[df['Corp Name'] == selected_corp_name]
    active_df = full_corp_history[full_corp_history['Status'].astype(str).str.contains("Active", case=False, na=False)]
    
    if not full_corp_history.empty:
        tab_overview, tab_weekly, tab_hof, tab_streaks, tab_profiles, tab_admin = st.tabs([
            "🏠 Overview", "📈 Weekly Gains", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"
        ])

        # --- TABS 1-4 (Standard Roster Views) ---
        # Note: These use 'active_df' to ensure only current members show in leaderboards
        with tab_overview:
            latest_date = active_df['Date'].max()
            latest_df = active_df[active_df['Date'] == latest_date]
            st.markdown(f'<div class="section-header">📈 {selected_corp_name} Roster ({latest_date.strftime("%Y-%m-%d")})</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Active Roster", f"{len(latest_df)}")
            m2.metric("Avg Level", f"{latest_df['Lvl'].mean():,.0f}")
            m3.metric("Total Value", f"${latest_df['CV'].sum():,.0f}M")
            m4.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}")
            st.dataframe(format_table(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], ['Lvl', 'CV', 'DC']), hide_index=True, use_container_width=True)

        with tab_weekly:
            all_weeks = sorted(active_df['Date'].unique(), reverse=True)
            sel_week = st.selectbox("Select Week:", [d.strftime("%Y-%m-%d") for d in all_weeks])
            week_data = active_df[active_df['Date'] == pd.to_datetime(sel_week)]
            w1, w2, w3 = st.columns(3)
            w1.subheader("📈 Lvl Gain")
            w1.dataframe(format_table(week_data[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False), ['Lvl Gain']), hide_index=True)
            w2.subheader("💰 CV Gain")
            w2.dataframe(format_table(week_data[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False), ['CV Gain']), hide_index=True)
            w3.subheader("💫 DC Gain")
            w3.dataframe(format_table(week_data[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False), ['DC Gain']), hide_index=True)

        with tab_hof:
            st.markdown('<div class="section-header">👑 All-Time Records (Active Members Only)</div>', unsafe_allow_html=True)
            h1, h2, h3 = st.columns(3)
            h1.dataframe(format_table(active_df.groupby('Player Name')['Lvl'].max().sort_values(ascending=False).reset_index(), ['Lvl']), hide_index=True)
            h2.dataframe(format_table(active_df.groupby('Player Name')['CV'].max().sort_values(ascending=False).reset_index(), ['CV']), hide_index=True)
            h3.dataframe(format_table(active_df.groupby('Player Name')['DC'].sum().sort_values(ascending=False).reset_index(), ['DC']), hide_index=True)

        with tab_streaks:
            # Simple streak logic
            distinct_weeks = sorted(active_df['Date'].unique(), reverse=True)
            streak_list = []
            for uid in active_df['UID'].unique():
                p_dates = set(active_df[active_df['UID'] == uid]['Date'])
                c = 0
                for w in distinct_weeks:
                    if w in p_dates: c += 1
                    else: break
                streak_list.append({"Player Name": active_df[active_df['UID']==uid]['Player Name'].iloc[0], "Weeks": c})
            st.dataframe(format_table(pd.DataFrame(streak_list).sort_values("Weeks", ascending=False), ["Weeks"]), hide_index=True)

        # --- TAB 5: PROFILES (Custom Sorting Applied Here) ---
        with tab_profiles:
            st.markdown('<div class="section-header">👤 Member Progression</div>', unsafe_allow_html=True)
            
            # SORTING LOGIC: Sort by Status (Active first), then by Name
            # We create a unique list of players with their current status
            player_status_df = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']]
            
            # Custom sort: Active < Inactive alphabetically, then Name alphabetically
            player_status_df = player_status_df.sort_values(by=['Status', 'Player Name'], ascending=[True, True])
            
            # Create a display list (optional: adds status tag to name in dropdown)
            player_options = player_status_df['Player Name'].tolist()
            
            sel_player = st.selectbox("Search Member:", player_options)
            p_history = full_corp_history[full_corp_history['Player Name'] == sel_player].sort_values('Date')
            
            # Graphs
            g1, g2, g3 = st.tabs(["📈 Weekly Lvl Gain", "💰 Weekly CV Gain", "💫 Weekly DC Gain"])
            with g1: st.plotly_chart(px.line(p_history, x='Date', y='Lvl Gain', markers=True), use_container_width=True)
            with g2: st.plotly_chart(px.line(p_history, x='Date', y='CV Gain', markers=True), use_container_width=True)
            with g3: st.plotly_chart(px.line(p_history, x='Date', y='DC Gain', markers=True), use_container_width=True)

            # Metrics
            st.write("---")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Status", p_history['Status'].iloc[-1])
            m_col2.metric("Current Lvl", f"{int(p_history['Lvl'].iloc[-1]):,}")
            m_col3.metric("Avg DC Gain", f"+{int(p_history['DC Gain'].mean()):,}")
            m_col4.metric("Total DC", f"{int(p_history['DC'].sum()):,}")

        # --- TAB 6: ADMIN ---
        with tab_admin:
            pwd = st.text_input("Password:", type="password")
            if pwd == st.secrets.get("admin_password", "rcttaddict"):
                with st.form("add_log"):
                    f1, f2 = st.columns(2)
                    d = f1.date_input("Date", date.today())
                    u = f1.text_input("UID")
                    c = f2.text_input("Corp ID", "CORP_001")
                    l = f2.number_input("Lvl", 1, 999, 100)
                    cv = f1.number_input("CV (M)", 0, 1000000, 1000)
                    dc = f2.number_input("Donations", 0, 1000000, 0)
                    if st.form_submit_button("Commit"):
                        stats_ws.append_row([str(d), c, u, int(l), int(cv), int(dc)])
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.warning("No data found.")
else:
    st.info("Awaiting data...")
