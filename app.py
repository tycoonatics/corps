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

# --- 2. CSS STYLING ---
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

        # Logic for gains: Only calculate gain if the date is consecutive (approx 7 days)
        # Otherwise, set gain to 0 to prevent the leave/rejoin reset spike
        stats_df['Days_Since_Last'] = stats_df.groupby('UID')['Date'].diff().dt.days
        
        def calculate_safe_gain(row, col):
            if row['Days_Since_Last'] > 10 or pd.isna(row['Days_Since_Last']):
                return 0
            return max(0, row[col + '_diff'])

        for col in ['Lvl', 'CV', 'DC']:
            stats_df[col + '_diff'] = stats_df.groupby('UID')[col].diff()
            stats_df[col + ' Gain'] = stats_df.apply(lambda r: calculate_safe_gain(r, col), axis=1)
            
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
    
    full_corp_history = df[df['Corp Name'] == selected_corp_name]
    active_df = full_corp_history[full_corp_history['Status'].astype(str).str.contains("Active", case=False, na=False)]
    
    if not full_corp_history.empty:
        tab_overview, tab_weekly, tab_hof, tab_streaks, tab_profiles, tab_admin = st.tabs([
            "🏠 Overview", "📈 Weekly Gains", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"
        ])

        # (Overview, Weekly, HOF, and Streaks logic as before)
        # ... [Standard Tabs 1-4] ...

        with tab_profiles:
            st.markdown('<div class="section-header">👤 Member Progression</div>', unsafe_allow_html=True)
            player_status_df = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']]
            player_status_df = player_status_df.sort_values(by=['Status', 'Player Name'], ascending=[True, True])
            player_options = player_status_df['Player Name'].tolist()
            
            sel_player = st.selectbox("Search Member:", player_options)
            p_history = full_corp_history[full_corp_history['Player Name'] == sel_player].sort_values('Date')
            
            # --- THE BREAK IN THE LINE FIX ---
            # Create a full date range for the corp to find the holes
            all_dates = pd.date_range(start=p_history['Date'].min(), end=p_history['Date'].max(), freq='W-MON')
            p_history_full = pd.DataFrame({'Date': all_dates})
            p_history_full = pd.merge(p_history_full, p_history, on='Date', how='left')
            
            g1, g2, g3 = st.tabs(["📈 Weekly Lvl Gain", "💰 Weekly CV Gain", "💫 Weekly DC Gain"])
            
            # Setting connectgaps=False creates the physical break in the line
            with g1:
                fig1 = px.line(p_history_full, x='Date', y='Lvl Gain', markers=True)
                fig1.update_traces(connectgaps=False)
                st.plotly_chart(fig1, use_container_width=True)
            with g2:
                fig2 = px.line(p_history_full, x='Date', y='CV Gain', markers=True)
                fig2.update_traces(connectgaps=False)
                st.plotly_chart(fig2, use_container_width=True)
            with g3:
                fig3 = px.line(p_history_full, x='Date', y='DC Gain', markers=True)
                fig3.update_traces(connectgaps=False)
                st.plotly_chart(fig3, use_container_width=True)

            st.write("---")
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Status", p_history['Status'].iloc[-1])
            m_col2.metric("Total Lvl Gain", f"+{int(p_history['Lvl Gain'].sum()):,}")
            m_col3.metric("Avg Weekly DC", f"+{int(p_history['DC Gain'].mean()):,}")
            m_col4.metric("Total DC Contribution", f"{int(p_history['DC Gain'].sum()):,}")

        # (Admin Tab remains as before)
        # ... [Admin Tab] ...
