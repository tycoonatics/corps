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

# --- 3. DATABASE CONNECTION & DATA SANITIZATION ---
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

        # SPIKE PROTECTION
        stats_df['Days_Gap'] = stats_df.groupby('UID')['Date'].diff().dt.days
        
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[f'{col}_Raw_Diff'] = stats_df.groupby('UID')[col].diff()
            
            def sanitize_gains(row, column):
                diff = row[f'{column}_Raw_Diff']
                gap = row['Days_Gap']
                
                # Basic check for gaps or negative values
                if pd.isna(diff) or diff < 0 or gap > 10:
                    return 0
                
                # Strict Thresholds for Spikes
                if column == 'DC' and diff > 150000:
                    return 0
                if column == 'CV' and diff > 100000: # FIX: Prevents the 400k+ CV spike
                    return 0
                    
                return diff

            stats_df[f'{col} Gain'] = stats_df.apply(lambda r: sanitize_gains(r, col), axis=1).fillna(0)
            
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
        tabs = st.tabs(["🏠 Overview", "📈 Weekly Gains", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"])

        # (Other tabs logic...)
        # ...

        # TAB 5: PROFILES
        with tabs[4]:
            st.markdown('<div class="section-header">👤 Member Progression</div>', unsafe_allow_html=True)
            player_status_df = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']]
            player_status_df = player_status_df.sort_values(by=['Status', 'Player Name'], ascending=[True, True])
            sel_player = st.selectbox("Search Member:", player_status_df['Player Name'].tolist())
            
            p_history = full_corp_history[full_corp_history['Player Name'] == sel_player].sort_values('Date')
            
            # Gap detection for visual breaks
            all_dates = pd.date_range(start=p_history['Date'].min(), end=p_history['Date'].max(), freq='W-MON')
            p_history_full = pd.DataFrame({'Date': all_dates}).merge(p_history, on='Date', how='left')

            sub_tabs = st.tabs(["📈 Weekly Lvl Gain", "💰 Weekly CV Gain", "💫 Weekly DC Gain"])
            
            with sub_tabs[0]:
                st.plotly_chart(px.line(p_history_full, x='Date', y='Lvl Gain', markers=True).update_traces(connectgaps=False), use_container_width=True)
            with sub_tabs[1]:
                st.plotly_chart(px.line(p_history_full, x='Date', y='CV Gain', markers=True).update_traces(connectgaps=False), use_container_width=True)
            with sub_tabs[2]:
                st.plotly_chart(px.line(p_history_full, x='Date', y='DC Gain', markers=True).update_traces(connectgaps=False), use_container_width=True)

            st.write("---")
            m1, m2, m3, m4 = st.columns(4)
            
            # Use only weeks with actual activity for the average calculation
            active_dc_weeks = p_history[p_history['DC Gain'] > 0]
            avg_dc_val = active_dc_weeks['DC Gain'].mean() if not active_dc_weeks.empty else 0
            
            m1.metric("Status", p_history['Status'].iloc[-1])
            m2.metric("Total Lvl Gain", f"+{int(p_history['Lvl Gain'].sum()):,}")
            m3.metric("Avg Weekly DC", f"+{int(avg_dc_val):,}")
            m4.metric("Total DC Contribution", f"{int(p_history['DC Gain'].sum()):,}")

        # TAB 6: ADMIN (and others)
        # ...
    else:
        st.warning("No data found.")
else:
    st.info("Awaiting data...")
