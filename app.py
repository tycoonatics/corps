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

# --- 2. UPDATED CSS STYLING (Dark Mode Fix) ---
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
    /* Fixed Metric Card Styling for visibility in both light and dark themes */
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 15px;
        border-radius: 10px;
        color: inherit;
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
    
    active_df = df[df['Status'].astype(str).str.contains("Active", case=False, na=False)]
    corp_df = active_df[active_df['Corp Name'] == selected_corp_name].sort_values('Date', ascending=False)
    
    if not corp_df.empty:
        tab_overview, tab_weekly, tab_hof, tab_streaks, tab_profiles, tab_admin = st.tabs([
            "🏠 Overview", "📈 Weekly Gains", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"
        ])

        # ... (Overview, Weekly, HOF, Streaks logic remains the same as before) ...
        # [Omitting for brevity, but keep your current code for those tabs]

        with tab_profiles:
            st.markdown('<div class="section-header">👤 Individual Weekly Activity Tracker</div>', unsafe_allow_html=True)
            full_corp_history = df[df['Corp Name'] == selected_corp_name]
            all_players = sorted(full_corp_history['Player Name'].unique())
            sel_player = st.selectbox("Search Member:", all_players)
            p_history = full_corp_history[full_corp_history['Player Name'] == sel_player].sort_values('Date')
            
            # REORDERED FOR MOBILE VISIBILITY: Graphs first, Metrics below
            sub1, sub2, sub3 = st.tabs(["📈 Weekly Lvl Gain", "💰 Weekly CV Gain", "💫 Weekly DC Gain"])
            
            with sub1:
                st.plotly_chart(px.line(p_history, x='Date', y='Lvl Gain', markers=True, title="Activity: Lvl Gain"), use_container_width=True)
            with sub2:
                st.plotly_chart(px.line(p_history, x='Date', y='CV Gain', markers=True, title="Activity: CV Gain (M)"), use_container_width=True)
            with sub3:
                st.plotly_chart(px.line(p_history, x='Date', y='DC Gain', markers=True, title="Activity: DC Points"), use_container_width=True)

            st.write("---")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Status", p_history['Status'].iloc[-1])
            m_col2.metric("Current Lvl", f"{int(p_history['Lvl'].iloc[-1]):,}")
            m_col3.metric("Avg DC Gain", f"+{int(p_history['DC Gain'].mean()):,}")
            m_col4.metric("Total DC", f"{int(p_history['DC'].sum()):,}")

        # ... (Keep Tab Admin logic) ...

    else:
        st.warning(f"No active members found for {selected_corp_name}.")
else:
    st.info("System Ready. Please connect your spreadsheet.")
