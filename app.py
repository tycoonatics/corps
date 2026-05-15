import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import base64
import json
import plotly.express as px
import calendar

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="MPG RC Tycoons Hub", page_icon="🏆", layout="wide")

# --- 2. CSS STYLING ---
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px; border-radius: 15px; text-align: center;
        color: white; font-family: 'Arial Black', sans-serif; font-size: 2rem; margin-bottom: 30px;
    }
    div[data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 15px; border-radius: 10px;
    }
    .section-header {
        background-color: #e2e8f0; padding: 6px 12px; border-radius: 4px;
        font-weight: bold; margin-bottom: 10px; margin-top: 25px; color: #1e293b;
    }
    
    /* Elegant Dark-Mode Friendly Domain Headers */
    .domain-header {
        padding: 12px;
        border-radius: 8px 8px 0px 0px;
        text-align: center;
        font-weight: bold;
        color: #f8fafc;
        margin-top: 20px;
        font-size: 1.1rem;
        letter-spacing: 0.5px;
    }
    .lvl-bg { 
        background-color: rgba(14, 116, 144, 0.3); 
        border: 1px solid #06b6d4; 
        border-bottom: none;
    }
    .cv-bg { 
        background-color: rgba(21, 128, 61, 0.3); 
        border: 1px solid #10b981; 
        border-bottom: none;
    }
    .dc-bg { 
        background-color: rgba(161, 98, 7, 0.3); 
        border: 1px solid #eab308; 
        border-bottom: none;
    }
    
    .award-card {
        background: rgba(255, 215, 0, 0.1); border: 2px solid #ffd700;
        padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; min-height: 160px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 MPG RC TYCOONS KNOWLEDGE HUB </div>', unsafe_allow_html=True)

# --- 3. DATABASE & DATA PROCESSING ---
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

        # Gains Calculation
        stats_df['Days_Gap'] = stats_df.groupby('UID')['Date'].diff().dt.days
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[f'{col}_Raw_Diff'] = stats_df.groupby('UID')[col].diff()
            def sanitize(row, column):
                diff, gap = row[f'{column}_Raw_Diff'], row['Days_Gap']
                if pd.isna(diff) or diff < 0 or gap > 10: return 0
                if column == 'DC' and diff > 150000: return 0
                if column == 'CV' and diff > 100000: return 0
                return diff
            stats_df[f'{col} Gain'] = stats_df.apply(lambda r: sanitize(r, col), axis=1).fillna(0)
            
        return stats_df, raw_stats_ws, player_map, status_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}

df, stats_ws, player_map, status_map, corp_map = load_mapped_data()

def format_table(dataframe, columns):
    f_dict = {col: "{:,.0f}" for col in columns}
    for c in dataframe.columns:
        if any(x in c for x in ['Rank', 'Lvl', 'Weeks']):
            f_dict[c] = "{:.0f}"
    return dataframe.style.format(f_dict)

# --- GLOBAL PRE-CALCULATIONS ---
if not df.empty:
    df['L3'] = df.groupby('Date')['Lvl Gain'].rank(ascending=False, method='min') <= 3
    df['C3'] = df.groupby('Date')['CV Gain'].rank(ascending=False, method='min') <= 3
    df['D3'] = df.groupby('Date')['DC Gain'].rank(ascending=False, method='min') <= 3
    df['D1K'] = df['DC Gain'] >= 1000
    df['Month_Key'] = df['Date'].dt.to_period('M')

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    full_corp_history = df[df['Corp Name'] == selected_corp_name]
    active_df = full_corp_history[full_corp_history['Status'].astype(str).str.contains("Active", case=False, na=False)].copy()
    
    if not full_corp_history.empty:
        tabs = st.tabs(["🏠 Overview", "📈 Weekly Gains", "🗓️ Monthly", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"])

        # TAB 1: WEEKLY GAINS (As previously implemented)
        with tabs[1]:
            all_weeks = sorted(active_df['Date'].unique(), reverse=True)
            sel_week_str = st.selectbox("Select Week:", [d.strftime("%Y-%m-%d") for d in all_weeks], key="weekly_sel")
            week_data = active_df[active_df['Date'] == pd.to_datetime(sel_week_str)].copy()
            if not week_data.empty:
                st.markdown('<div class="section-header">🏅 Weekly Performance Awards</div>', unsafe_allow_html=True)
                w1, w2, w3 = st.columns(3)
                with w1:
                    st.markdown('<div class="domain-header lvl-bg">📈 Δ Level (Lvl)</div>', unsafe_allow_html=True)
                    l_board = week_data[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                    l_board.insert(0, 'Rank', l_board['Lvl Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(l_board, ['Lvl Gain']), hide_index=True, use_container_width=True)
                with w2:
                    st.markdown('<div class="domain-header cv-bg">💰 Δ Company Value (CV)</div>', unsafe_allow_html=True)
                    c_board = week_data[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                    c_board.insert(0, 'Rank', c_board['CV Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(c_board, ['CV Gain']), hide_index=True, use_container_width=True)
                with w3:
                    st.markdown('<div class="domain-header dc-bg">🎁 Δ Donation Count (DC)</div>', unsafe_allow_html=True)
                    d_board = week_data[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                    d_board.insert(0, 'Rank', d_board['DC Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(d_board, ['DC Gain']), hide_index=True, use_container_width=True)

        # TAB 2: MONTHLY (As previously implemented)
        with tabs[2]:
            st.markdown('<div class="section-header">🗓️ Monthly Performance & Awards</div>', unsafe_allow_html=True)
            m_opts = sorted(active_df['Month_Key'].unique(), reverse=True)
            sel_m = st.selectbox("Select Month:", m_opts, format_func=lambda x: x.strftime('%B %Y'))
            m_data = active_df[active_df['Month_Key'] == sel_m].copy()
            if not m_data.empty:
                m_totals = m_data.groupby('Player Name').agg({'Lvl Gain':'sum','CV Gain':'sum','DC Gain':'sum'}).reset_index()
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.markdown('<div class="domain-header lvl-bg">📈 Δ Level (Lvl)</div>', unsafe_allow_html=True)
                    ml_board = m_totals[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                    ml_board.insert(0, 'Rank', ml_board['Lvl Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(ml_board, ['Lvl Gain']), hide_index=True, use_container_width=True)
                with mc2:
                    st.markdown('<div class="domain-header cv-bg">💰 Δ Company Value (CV)</div>', unsafe_allow_html=True)
                    mc_board = m_totals[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                    mc_board.insert(0, 'Rank', mc_board['CV Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(mc_board, ['CV Gain']), hide_index=True, use_container_width=True)
                with mc3:
                    st.markdown('<div class="domain-header dc-bg">🎁 Δ Donation Count (DC)</div>', unsafe_allow_html=True)
                    md_board = m_totals[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                    md_board.insert(0, 'Rank', md_board['DC Gain'].rank(ascending=False, method='min'))
                    st.dataframe(format_table(md_board, ['DC Gain']), hide_index=True, use_container_width=True)

        # TAB 3: HALL OF FAME
        with tabs[3]:
            st.markdown('<div class="section-header">👑 Lifetime Growth (Active Members)</div>', unsafe_allow_html=True)
            hof = active_df.groupby('Player Name')[['Lvl Gain', 'CV Gain', 'DC Gain']].sum().reset_index()
            
            h1, h2, h3 = st.columns(3)
            with h1:
                st.markdown('<div class="domain-header lvl-bg">📈 Lifetime Δ Level</div>', unsafe_allow_html=True)
                h_lvl = hof[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                h_lvl.insert(0, 'Rank', h_lvl['Lvl Gain'].rank(ascending=False, method='min'))
                st.dataframe(format_table(h_lvl, ['Lvl Gain']), hide_index=True, use_container_width=True)
            with h2:
                st.markdown('<div class="domain-header cv-bg">💰 Lifetime Δ Company Value</div>', unsafe_allow_html=True)
                h_cv = hof[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                h_cv.insert(0, 'Rank', h_cv['CV Gain'].rank(ascending=False, method='min'))
                st.dataframe(format_table(h_cv, ['CV Gain']), hide_index=True, use_container_width=True)
            with h3:
                st.markdown('<div class="domain-header dc-bg">🎁 Lifetime Δ Donations</div>', unsafe_allow_html=True)
                h_dc = hof[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                h_dc.insert(0, 'Rank', h_dc['DC Gain'].rank(ascending=False, method='min'))
                st.dataframe(format_table(h_dc, ['DC Gain']), hide_index=True, use_container_width=True)

        # (Remaining tabs 0, 4, 5, 6 remain as previously implemented)
