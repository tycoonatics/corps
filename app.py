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
st.set_page_config(page_title="RCT Touch Analytics", page_icon="📊", layout="wide")

# --- 2. FLOATING ELEMENT MASK & ADVANCED BRANDING CLOAK ---
st.markdown("""
    <style>
    /* 1. Nuke standard internal layout targets */
    [data-testid="stHeader"], header, footer, .stAppFooter, #MainMenu, [data-testid="stDecoration"],
    button[title="Collapse sidebar"], input[aria-label="Show sidebar"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
    
    /* 2. FORCE THE APP TO CLOAK THE OUTER WRAPPER CONTAINER */
    /* This forces the app viewport to paint cleanly over the iframe edges */
    .stApp {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 999999 !important;
        background-color: #0e1117 !important;
    }
    
    /* Fix standard container scroll behaviors inside the forced fullscreen layout */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        overflow-y: auto !important;
        height: 100vh !important;
    }
    
    /* 3. Custom Dashboard UI Theme Elements */
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
    
    /* Domain Track Tables Styling */
    .domain-header {
        padding: 12px; border-radius: 8px 8px 0px 0px; text-align: center;
        font-weight: bold; color: #f8fafc; margin-top: 20px; font-size: 1.1rem; letter-spacing: 0.5px;
    }
    .lvl-bg { background-color: rgba(14, 116, 144, 0.3); border: 1px solid #06b6d4; border-bottom: none; }
    .cv-bg { background-color: rgba(21, 128, 61, 0.3); border: 1px solid #10b981; border-bottom: none; }
    .dc-bg { background-color: rgba(161, 98, 7, 0.3); border: 1px solid #eab308; border-bottom: none; }
    .overall-bg { background-color: rgba(147, 51, 234, 0.3); border: 1px solid #a855f7; border-bottom: none; }
    .award-card { background: rgba(255, 215, 0, 0.1); border: 2px solid #ffd700; padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; min-height: 160px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📊 RCT Touch Corp Analytics</div>', unsafe_allow_html=True)

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
    f_dict = {col: "{:,.1f}" for col in columns}
    for c in dataframe.columns:
        if any(x in c for x in ['Rank', 'Weeks']):
            f_dict[c] = "{:.0f}"
    return dataframe.style.format(f_dict)

def format_table_absolute(dataframe, columns):
    f_dict = {col: "{:,.0f}" for col in columns}
    for c in dataframe.columns:
        if any(x in c for x in ['Rank', 'Lvl', 'Weeks', 'Score']):
            f_dict[c] = "{:.0f}"
    return dataframe.style.format(f_dict)

# --- GLOBAL PRE-CALCULATIONS ---
if not df.empty:
    df['L3'] = df.groupby('Date')['Lvl Gain'].rank(ascending=False, method='min') <= 3
    df['C3'] = df.groupby('Date')['CV Gain'].rank(ascending=False, method='min') <= 3
    df['D3'] = df.groupby('Date')['DC Gain'].rank(ascending=False, method='min') <= 3
    df['D1K'] = df['DC Gain'] >= 1000
    df['Month_Key'] = df['Date'].dt.to_period('M')

    # Simulate weekly award winners
    award_winners = []
    for d in df['Date'].unique():
        wk = df[df['Date'] == d].copy()
        if not wk.empty:
            wk['LR'] = wk['Lvl Gain'].rank(ascending=False, method='min')
            wk['CR'] = wk['CV Gain'].rank(ascending=False, method='min')
            wk['DR'] = wk['DC Gain'].rank(ascending=False, method='min')
            wk['RS_Score'] = wk['LR'] + wk['CR'] + wk['DR']
            rs_winner = wk.sort_values(['RS_Score', 'DC Gain'], ascending=[True, False]).iloc[0]['Player Name']
            
            l_cut = wk['Lvl'].quantile(0.35)
            rookies = wk[wk['Lvl'] <= l_cut]
            rotw_winner = rookies.sort_values('DC Gain', ascending=False).iloc[0]['Player Name'] if not rookies.empty else None
            award_winners.append({'Date': d, 'RS_Winner': rs_winner, 'RotW_Winner': rotw_winner})
            
    df = df.merge(pd.DataFrame(award_winners), on='Date', how='left')
    df['is_RS'] = df['Player Name'] == df['RS_Winner']
    df['is_RotW'] = df['Player Name'] == df['RotW_Winner']

    # Helper function for calculating simple streaks
    def get_longest_streak(history_list):
        longest, current = 0, 0
        for val in history_list:
            if val:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    # Advanced Engine: Parses history and returns detailed list of individual streak blocks
    def calculate_streak_details(player_df, metric_col, type_label, latest_corp_date):
        p_sorted = player_df.sort_values('Date', ascending=True)
        streaks = []
        current_streak = []
        
        for idx, row in p_sorted.iterrows():
            if row[metric_col]:
                current_streak.append(row['Date'])
            else:
                if current_streak:
                    streaks.append({
                        "Type": type_label,
                        "Name": row['Player Name'],
                        "Weeks": len(current_streak),
                        "Start Date": current_streak[0],
                        "End Date": current_streak[-1],
                        "Is Active": current_streak[-1] == latest_corp_date
                    })
                    current_streak = []
        if current_streak:
            streaks.append({
                "Type": type_label,
                "Name": p_sorted.iloc[-1]['Player Name'],
                "Weeks": len(current_streak),
                "Start Date": current_streak[0],
                "End Date": current_streak[-1],
                "Is Active": p_sorted.iloc[-1]['Date'] == latest_corp_date and p_sorted.iloc[-1][metric_col]
            })
        return streaks

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    full_corp_history = df[df['Corp Name'] == selected_corp_name]
    
    # Identify players who are strictly active based on their LATEST log entry
    latest_player_snapshots = full_corp_history.sort_values('Date').groupby('Player Name').last().reset_index()
    active_player_names = latest_player_snapshots[latest_player_snapshots['Status'].astype(str).str.contains("Active", case=False, na=False)]['Player Name'].tolist()
    
    # Slice full historical log to include ONLY the records belonging to currently active players
    active_df = full_corp_history[full_corp_history['Player Name'].isin(active_player_names)].copy()
    
    if not full_corp_history.empty:
        # Layout View Tabs
        tabs = st.tabs(["🏠 Overview", "🏆 Leaderboards", "🏋️ true-grind-index", "🔥 Streaks", "👤 Profiles", "🔑 Admin"])

        # TAB 0: OVERVIEW
        with tabs[0]:
            latest_date = active_df['Date'].max()
            latest_df = active_df[active_df['Date'] == latest_date]
            st.markdown(f'<div class="section-header">📈 {selected_corp_name} Roster ({latest_date.strftime("%Y-%m-%d")})</div>', unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Active Roster", f"{len(latest_df)}")
            m2.metric("Avg Level", f"{latest_df['Lvl'].mean():,.0f}")
            m3.metric("Total Value", f"${latest_df['CV'].sum():,.0f}M")
            m4.metric("Total Donations", f"{latest_df['DC'].sum():,.0f}")
            st.dataframe(format_table_absolute(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], ['Lvl', 'CV', 'DC']), hide_index=True, use_container_width=True)

        # TAB 1: LEADERBOARDS HUB (WEEKLY, MONTHLY, ANNUAL, ALL-TIME SUB-VIEWS)
        with tabs[1]:
            board_view = st.radio(
                "Select Leaderboard Filter Scope:",
                ["📈 Weekly Performance", "🗓️ Monthly Summary", "📅 Annual Growth", "👑 All-Time Standings"],
                horizontal=True
            )
            st.markdown("---")

            # SUB-VIEW A: WEEKLY GAINS
            if board_view == "📈 Weekly Performance":
                all_weeks = sorted(active_df['Date'].unique(), reverse=True)
                sel_week_str = st.selectbox("Select Week:", [d.strftime("%Y-%m-%d") for d in all_weeks], key="weekly_sel")
                week_data = active_df[active_df['Date'] == pd.to_datetime(sel_week_str)].copy()
                if not week_data.empty:
                    st.markdown('<div class="section-header">🏅 Weekly Performance Awards</div>', unsafe_allow_html=True)
                    rotw_w = week_data['RotW_Winner'].iloc[0]
                    rs_w = week_data['RS_Winner'].iloc[0]
                    a1, a2 = st.columns(2)
                    if rotw_w:
                        a1.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🐣 Rookie of the Week</h3><h1>{rotw_w}</h1></div>', unsafe_allow_html=True)
                    a2.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🚀 Rising Star</h3><h1>{rs_w}</h1></div>', unsafe_allow_html=True)
                    
                    w1, w2, w3 = st.columns(3)
                    with w1:
                        st.markdown('<div class="domain-header lvl-bg">📈 Δ Level (Lvl)</div>', unsafe_allow_html=True)
                        l_board = week_data[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                        l_board.insert(0, 'Rank', l_board['Lvl Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(l_board, ['Lvl Gain']), hide_index=True, use_container_width=True)
                    with w2:
                        st.markdown('<div class="domain-header cv-bg">💰 Δ Company Value (CV)</div>', unsafe_allow_html=True)
                        c_board = week_data[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                        c_board.insert(0, 'Rank', c_board['CV Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(c_board, ['CV Gain']), hide_index=True, use_container_width=True)
                    with w3:
                        st.markdown('<div class="domain-header dc-bg">🎁 Δ Donation Count (DC)</div>', unsafe_allow_html=True)
                        d_board = week_data[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                        d_board.insert(0, 'Rank', d_board['DC Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(d_board, ['DC Gain']), hide_index=True, use_container_width=True)

            # SUB-VIEW B: MONTHLY SUMMARY
            elif board_view == "🗓️ Monthly Summary":
                st.markdown('<div class="section-header">🗓️ Monthly Performance & Awards</div>', unsafe_allow_html=True)
                m_opts = sorted(active_df['Month_Key'].unique(), reverse=True)
                sel_m = st.selectbox("Select Month:", m_opts, format_func=lambda x: x.strftime('%B %Y'))
                m_data = active_df[active_df['Month_Key'] == sel_m].copy()
                y, m = sel_m.year, sel_m.month
                total_m = len([1 for i in calendar.monthcalendar(y, m) if i[0] != 0])
                recorded = m_data['Date'].nunique()
                st.write(f"**Month Progress:** {recorded} / {total_m} Weeks Recorded")
                if not m_data.empty:
                    m_totals = m_data.groupby('Player Name').agg({'Lvl Gain':'sum','CV Gain':'sum','DC Gain':'sum','Lvl':'min'}).reset_index()
                    if recorded >= total_m:
                        st.markdown('<div class="section-header">🏆 Monthly Winners</div>', unsafe_allow_html=True)
                        ac1, ac2, ac3 = st.columns(3)
                        sr = m_totals.sort_values('Lvl Gain', ascending=False).iloc[0]
                        en = m_totals.sort_values('CV Gain', ascending=False).iloc[0]
                        mvp = m_totals.sort_values('DC Gain', ascending=False).iloc[0]
                        ac1.markdown(f'<div class="award-card"><h3>👟 Speed Runner</h3><h1>{sr["Player Name"]}</h1></div>', unsafe_allow_html=True)
                        ac2.markdown(f'<div class="award-card"><h3>🏢 Entrepreneurship</h3><h1>{en["Player Name"]}</h1></div>', unsafe_allow_html=True)
                        ac3.markdown(f'<div class="award-card"><h3>⭐ MVP</h3><h1>{mvp["Player Name"]}</h1></div>', unsafe_allow_html=True)
                    
                    mc1, mc2, mc3 = st.columns(3)
                    with mc1:
                        st.markdown('<div class="domain-header lvl-bg">📈 Δ Level (Lvl)</div>', unsafe_allow_html=True)
                        ml_board = m_totals[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                        ml_board.insert(0, 'Rank', ml_board['Lvl Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(ml_board, ['Lvl Gain']), hide_index=True, use_container_width=True)
                    with mc2:
                        st.markdown('<div class="domain-header cv-bg">💰 Δ Company Value (CV)</div>', unsafe_allow_html=True)
                        mc_board = m_totals[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                        mc_board.insert(0, 'Rank', mc_board['CV Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(mc_board, ['CV Gain']), hide_index=True, use_container_width=True)
                    with mc3:
                        st.markdown('<div class="domain-header dc-bg">🎁 Δ Donation Count (DC)</div>', unsafe_allow_html=True)
                        md_board = m_totals[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                        md_board.insert(0, 'Rank', md_board['DC Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(md_board, ['DC Gain']), hide_index=True, use_container_width=True)

            # SUB-VIEW C: ANNUAL GROWTH
            elif board_view == "📅 Annual Growth":
                st.markdown('<div class="section-header">👑 Annual Growth Standings (Active Members)</div>', unsafe_allow_html=True)
                available_years = sorted(active_df['Date'].dt.year.unique(), reverse=True)
                if not available_years:
                    available_years = [2026, 2025]
                    
                selected_year = st.selectbox("Select Calendar Year:", available_years, key="annual_year_sel")
                annual_df = active_df[active_df['Date'].dt.year == selected_year].copy()
                
                if not annual_df.empty:
                    annual_hof = annual_df.groupby('Player Name')[['Lvl Gain', 'CV Gain', 'DC Gain']].sum().reset_index()
                    
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        st.markdown(f'<div class="domain-header lvl-bg">📈 {selected_year} Total Δ Level</div>', unsafe_allow_html=True)
                        h_lvl = annual_hof[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False)
                        h_lvl.insert(0, 'Rank', h_lvl['Lvl Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(h_lvl, ['Lvl Gain']), hide_index=True, use_container_width=True)
                    with h2:
                        st.markdown(f'<div class="domain-header cv-bg">💰 {selected_year} Total Δ Company Value</div>', unsafe_allow_html=True)
                        h_cv = annual_hof[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False)
                        h_cv.insert(0, 'Rank', h_cv['CV Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(h_cv, ['CV Gain']), hide_index=True, use_container_width=True)
                    with h3:
                        st.markdown(f'<div class="domain-header dc-bg">🎁 {selected_year} Total Δ Donations</div>', unsafe_allow_html=True)
                        h_dc = annual_hof[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False)
                        h_dc.insert(0, 'Rank', h_dc['DC Gain'].rank(ascending=False, method='min'))
                        st.dataframe(format_table_absolute(h_dc, ['DC Gain']), hide_index=True, use_container_width=True)
                else:
                    st.warning(f"No logged data records available for the year {selected_year}.")

            # SUB-VIEW D: ALL-TIME STANDINGS
            elif board_view == "👑 All-Time Standings":
                st.markdown('<div class="section-header">👑 All-Time Standings (Active Members Only)</div>', unsafe_allow_html=True)
                current_snapshots = latest_player_snapshots[latest_player_snapshots['Status'].astype(str).str.contains("Active", case=False, na=False)].copy()
                
                if not current_snapshots.empty:
                    current_snapshots['L_Rank'] = current_snapshots['Lvl'].rank(ascending=False, method='min')
                    current_snapshots['C_Rank'] = current_snapshots['CV'].rank(ascending=False, method='min')
                    current_snapshots['D_Rank'] = current_snapshots['DC'].rank(ascending=False, method='min')
                    current_snapshots['Rank_Sum'] = current_snapshots['L_Rank'] + current_snapshots['C_Rank'] + current_snapshots['D_Rank']
                    current_snapshots['Overall_Rank'] = current_snapshots['Rank_Sum'].rank(ascending=True, method='min')
                    
                    st.markdown('<div class="domain-header overall-bg">👑 Master Overall Standings</div>', unsafe_allow_html=True)
                    master_board = current_snapshots[['Overall_Rank', 'Player Name', 'L_Rank', 'Lvl', 'C_Rank', 'CV', 'D_Rank', 'DC']].sort_values('Overall_Rank')
                    master_board.rename(columns={'Overall_Rank': 'Overall Rank', 'L_Rank': 'Lvl Rank', 'C_Rank': 'CV Rank', 'D_Rank': 'DC Rank'}, inplace=True)
                    
                    styled_master = format_table_absolute(master_board, ['Lvl', 'CV', 'DC'])
                    styled_master = styled_master.map(lambda v: 'background-color: rgba(147, 51, 234, 0.15); font-weight: bold;', subset=['Overall Rank'])
                    
                    st.dataframe(
                        styled_master,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Overall Rank": st.column_config.NumberColumn("🏅 Overall Rank"),
                            "Player Name": st.column_config.TextColumn("Player Name"),
                            "Lvl Rank": st.column_config.NumberColumn("📊 Lvl Rank"),
                            "Lvl": st.column_config.NumberColumn("Lvl    |"),
                            "CV Rank": st.column_config.NumberColumn("💰 CV Rank"),
                            "CV": st.column_config.NumberColumn("CV (M)    |"),
                            "DC Rank": st.column_config.NumberColumn("🎁 DC Rank"),
                            "DC": st.column_config.NumberColumn("Total DC")
                        }
                    )
                    
                    al_c1, al_c2, al_c3 = st.columns(3)
                    with al_c1:
                        st.markdown('<div class="domain-header lvl-bg">📈 All-Time Level (Lvl)</div>', unsafe_allow_html=True)
                        al_lvl = current_snapshots[['L_Rank', 'Player Name', 'Lvl']].sort_values('L_Rank')
                        al_lvl.rename(columns={'L_Rank': 'Rank'}, inplace=True)
                        st.dataframe(format_table_absolute(al_lvl, ['Lvl']), hide_index=True, use_container_width=True)
                    with al_c2:
                        st.markdown('<div class="domain-header cv-bg">💰 All-Time Company Value (CV)</div>', unsafe_allow_html=True)
                        al_cv = current_snapshots[['C_Rank', 'Player Name', 'CV']].sort_values('C_Rank')
                        al_cv.rename(columns={'C_Rank': 'Rank'}, inplace=True)
                        st.dataframe(format_table_absolute(al_cv, ['CV']), hide_index=True, use_container_width=True)
                    with al_c3:
                        st.markdown('<div class="domain-header dc-bg">🎁 All-Time Donations (DC)</div>', unsafe_allow_html=True)
                        al_dc = current_snapshots[['D_Rank', 'Player Name', 'DC']].sort_values('D_Rank')
                        al_dc.rename(columns={'D_Rank': 'Rank'}, inplace=True)
                        st.dataframe(format_table_absolute(al_dc, ['DC']), hide_index=True, use_container_width=True)

        # TAB 2: TRUE GRIND INDEX (AVERAGE WEEKLY PERFORMANCE)
        with tabs[2]:
            st.markdown('<div class="section-header">🏋️ True Grind Index (Historical Weekly Averages)</div>', unsafe_allow_html=True)
            
            if not active_df.empty:
                lvl_grind_df = active_df[~((active_df['Lvl'] >= 999) & (active_df['Lvl Gain'] == 0))]
                
                lvl_avg = lvl_grind_df.groupby('Player Name')['Lvl Gain'].mean().reset_index().rename(columns={'Lvl Gain': 'Avg Lvl Gain'})
                cv_avg = active_df.groupby('Player Name')['CV Gain'].mean().reset_index().rename(columns={'CV Gain': 'Avg CV Gain'})
                dc_avg = active_df.groupby('Player Name')['DC Gain'].mean().reset_index().rename(columns={'DC Gain': 'Avg DC Gain'})
                
                grind_df = lvl_avg.merge(cv_avg, on='Player Name', how='inner').merge(dc_avg, on='Player Name', how='inner').fillna(0)
                
                grind_df['L_Grind_Rank'] = grind_df['Avg Lvl Gain'].rank(ascending=False, method='min')
                grind_df['C_Grind_Rank'] = grind_df['Avg CV Gain'].rank(ascending=False, method='min')
                grind_df['D_Grind_Rank'] = grind_df['Avg DC Gain'].rank(ascending=False, method='min')
                
                tg_c1, tg_c2, tg_c3 = st.columns(3)
                
                with tg_c1:
                    st.markdown('<div class="domain-header lvl-bg">📈 Avg Weekly Δ Level (999 Cap Shielded)</div>', unsafe_allow_html=True)
                    tg_lvl = grind_df[['L_Grind_Rank', 'Player Name', 'Avg Lvl Gain']].sort_values('L_Grind_Rank')
                    tg_lvl.rename(columns={'L_Grind_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(tg_lvl, ['Avg Lvl Gain']), hide_index=True, use_container_width=True)
                    
                with tg_c2:
                    st.markdown('<div class="domain-header cv-bg">💰 Avg Weekly Δ Company Value</div>', unsafe_allow_html=True)
                    tg_cv = grind_df[['C_Grind_Rank', 'Player Name', 'Avg CV Gain']].sort_values('C_Grind_Rank')
                    tg_cv.rename(columns={'C_Grind_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(tg_cv, ['Avg CV Gain']), hide_index=True, use_container_width=True)
                    
                with tg_c3:
                    st.markdown('<div class="domain-header dc-bg">🎁 Avg Weekly Δ Donations</div>', unsafe_allow_html=True)
                    tg_dc = grind_df[['D_Grind_Rank', 'Player Name', 'Avg DC Gain']].sort_values('D_Grind_Rank')
                    tg_dc.rename(columns={'D_Grind_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(tg_dc, ['Avg DC Gain']), hide_index=True, use_container_width=True)

        # TAB 3: STREAKS
        with tabs[3]:
            st.markdown('<div class="section-header">🔥 Elite Performance Streaks</div>', unsafe_allow_html=True)
            st.caption("Format: Active (Longest Ever)")

            metric_map = {
                'L3': 'Δ Lvl',
                'C3': 'Δ CV',
                'D3': 'Δ DC',
                'D1K': '1k+ DC',
                'is_RotW': 'RotW',
                'is_RS': 'RS'
            }

            max_corp_date = active_df['Date'].max()

            final_s = []
            all_historical_streaks = []

            for uid in active_df['UID'].unique():
                p_h = active_df[active_df['UID'] == uid]
                p_name = p_h['Player Name'].iloc[0]
                
                history_metrics = {}
                for col_key, label in metric_map.items():
                    history_metrics[col_key] = p_h.sort_values('Date', ascending=True)[col_key].tolist()
                    extracted = calculate_streak_details(p_h, col_key, label, max_corp_date)
                    all_historical_streaks.extend(extracted)

                def stringify_streaks(history_list):
                    act, lng, run = 0, 0, 0
                    for val in history_list:
                        if val:
                            run += 1
                            lng = max(lng, run)
                        else:
                            run = 0
                    for val in reversed(history_list):
                        if val: act += 1
                        else: break
                    return f"{act} ({lng})"

                final_s.append({
                    "Player Name": p_name,
                    "Lvl Top 3": stringify_streaks(history_metrics['L3']),
                    "CV Top 3": stringify_streaks(history_metrics['C3']),
                    "DC Top 3": stringify_streaks(history_metrics['D3']),
                    "1,000+ DC": stringify_streaks(history_metrics['D1K']),
                    "RotW": stringify_streaks(history_metrics['is_RotW']),
                    "Rising Star": stringify_streaks(history_metrics['is_RS'])
                })
            
            s_df = pd.DataFrame(final_s)
            s_df['sort_val'] = s_df['DC Top 3'].apply(lambda x: int(x.split()[0]))
            st.dataframe(s_df.sort_values("sort_val", ascending=False).drop(columns=['sort_val']), 
                         hide_index=True, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("---")
            
            if all_historical_streaks:
                master_streak_df = pd.DataFrame(all_historical_streaks)
                
                active_streaks_df = master_streak_df[master_streak_df['Is Active'] == True].copy()
                active_streaks_df = active_streaks_df.sort_values('Weeks', ascending=False).head(10)
                active_streaks_display = active_streaks_df[['Type', 'Name', 'Weeks', 'Start Date']].copy()
                active_streaks_display['Start Date'] = active_streaks_display['Start Date'].dt.strftime('%m/%d/%Y')
                active_streaks_display.rename(columns={'Type': 'TypeName', 'Name': 'Name', 'Weeks': 'Weeks', 'Start Date': 'Start Date'}, inplace=True)
                
                longest_streaks_df = master_streak_df.sort_values('Weeks', ascending=False).head(10).copy()
                longest_streaks_df['End Date Presentation'] = longest_streaks_df.apply(
                    lambda row: "Streak Active!" if row['Is Active'] else row['End Date'].strftime('%m/%d/%Y'), axis=1
                )
                longest_streaks_df['Start Date'] = longest_streaks_df['Start Date'].dt.strftime('%m/%d/%Y')
                
                longest_display = longest_streaks_df[['Type', 'Name', 'Weeks', 'Start Date', 'End Date Presentation']].rename(
                    columns={'Type': 'TypeName', 'Name': 'Name', 'Weeks': 'Weeks', 'Start Date': 'Start Date', 'End Date Presentation': 'End Date'}
                )
                
                c_streak_1, c_streak_2 = st.columns(2)
                with c_streak_1:
                    st.markdown('### 🔥 Top Active Streaks')
                    st.dataframe(active_streaks_display, hide_index=True, use_container_width=True)
                    
                with c_streak_2:
                    st.markdown('### 👑 Top Longest Streaks')
                    st.dataframe(longest_display, hide_index=True, use_container_width=True)

        # TAB 4: PROFILES
        with tabs[4]:
            p_status = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']].sort_values(['Status', 'Player Name'])
            sel_p = st.selectbox("Search Member:", p_status['Player Name'].tolist(), key="p_sel")
            p_hist = full_corp_history[full_corp_history['Player Name'] == sel_p].sort_values('Date')
            m_hist = p_hist.groupby('Month_Key')[['Lvl Gain', 'CV Gain', 'DC Gain']].sum().reset_index()

            st.markdown('<div class="section-header">👤 Member Progression</div>', unsafe_allow_html=True)
            chart_dimension = st.radio("Select Domain Metric Visual:", ["Lvl Gain", "CV Gain", "DC Gain"], horizontal=True)
            st.plotly_chart(px.line(p_hist, x='Date', y=chart_dimension, title=f"Weekly {chart_dimension} History", markers=True), use_container_width=True)
            
            c_records, c_awards, c_streaks = st.columns(3)
            with c_records:
                st.subheader("🥇 Personal Bests")
                def get_best_with_date(df_source, target_col, time_col, is_month=False):
                    if df_source.empty or df_source[target_col].max() == 0:
                        return "N/A"
                    idx = df_source[target_col].idxmax()
                    val = df_source.loc[idx, target_col]
                    t_val = df_source.loc[idx, time_col]
                    t_str = t_val.strftime('%B %Y') if is_month else t_val.strftime('%Y-%m-%d')
                    prefix = "+$" if "CV" in target_col else "+" if "Lvl" in target_col else ""
                    suffix = "M" if "CV" in target_col else ""
                    return f"{prefix}{int(val):,}{suffix} ({t_str})"

                st.write(f"**Best Week (Lvl):** {get_best_with_date(p_hist, 'Lvl Gain', 'Date')}")
                st.write(f"**Best Month (Lvl):** {get_best_with_date(m_hist, 'Lvl Gain', 'Month_Key', is_month=True)}")
                st.write(f"**Best Week (CV):** {get_best_with_date(p_hist, 'CV Gain', 'Date')}")
                st.write(f"**Best Month (CV):** {get_best_with_date(m_hist, 'CV Gain', 'Month_Key', is_month=True)}")
                st.write(f"**Best Week (DC):** {get_best_with_date(p_hist, 'DC Gain', 'Date')}")
                st.write(f"**Best Month (DC):** {get_best_with_date(m_hist, 'DC Gain', 'Month_Key', is_month=True)}")

            with c_awards:
                st.subheader("👑 Career Award Wins")
                st.write(f"🏆 **Lvl Top 3 Finishes:** {p_hist['L3'].sum()}")
                st.write(f"🏆 **CV Top 3 Finishes:** {p_hist['C3'].sum()}")
                st.write(f"🏆 **DC Top 3 Finishes:** {p_hist['D3'].sum()}")
                st.write(f"🏆 **Rookie of the Week:** {p_hist['is_RotW'].sum()}")
                st.write(f"🏆 **Rising Star:** {p_hist['is_RS'].sum()}")

            with c_streaks:
                st.subheader("🔥 Longest Streaks")
                p_chron = p_hist.sort_values('Date', ascending=True)
                st.write(f"⚡ **Lvl Top 3 Streak:** {get_longest_streak(p_chron['L3'].tolist())} Weeks")
                st.write(f"⚡ **CV Top 3 Streak:** {get_longest_streak(p_chron['C3'].tolist())} Weeks")
                st.write(f"⚡ **DC Top 3 Streak:** {get_longest_streak(p_chron['D3'].tolist())} Weeks")
                st.write(f"⚡ **1,000+ DC Baseline:** {get_longest_streak(p_chron['D1K'].tolist())} Weeks")
                st.write(f"⚡ **Rookie of the Week:** {get_longest_streak(p_chron['is_RotW'].tolist())} Weeks")
                st.write(f"⚡ **Rising Star:** {get_longest_streak(p_chron['is_RS'].tolist())} Weeks")

        # TAB 5: ADMIN
        with tabs[5]:
            if st.text_input("Password:", type="password") == st.secrets.get("admin_password", "rcttaddict"):
                with st.form("add_log"):
                    f1, f2 = st.columns(2)
                    d, u, c = f1.date_input("Date", date.today()), f1.text_input("UID"), f2.text_input("Corp ID", "CORP_001")
                    l, cv, dc = f2.number_input("Lvl", 1, 999, 100), f1.number_input("CV (M)", 0, 1000000, 1000), f2.number_input("DC", 0, 1000000, 0)
                    if st.form_submit_button("Commit"):
                        stats_ws.append_row([str(d), c, u, int(l), int(cv), int(dc)])
                        st.cache_data.clear()
                        st.rerun()
    else: st.warning("No data found.")
else: st.info("Awaiting connection to database...")
