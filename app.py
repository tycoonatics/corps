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
    .award-card {
        background: rgba(255, 215, 0, 0.1);
        border: 2px solid #ffd700;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        min-height: 160px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 MPG RC TYCOONS KNOWLEDGE HUB </div>', unsafe_allow_html=True)

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

        # SPIKE PROTECTION & GAINS
        stats_df['Days_Gap'] = stats_df.groupby('UID')['Date'].diff().dt.days
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[f'{col}_Raw_Diff'] = stats_df.groupby('UID')[col].diff()
            def sanitize_gains(row, column):
                diff, gap = row[f'{column}_Raw_Diff'], row['Days_Gap']
                if pd.isna(diff) or diff < 0 or gap > 10: return 0
                if column == 'DC' and diff > 150000: return 0
                if column == 'CV' and diff > 100000: return 0
                return diff
            stats_df[f'{col} Gain'] = stats_df.apply(lambda r: sanitize_gains(r, col), axis=1).fillna(0)
            
        return stats_df, raw_stats_ws, player_map, status_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}

df, stats_ws, player_map, status_map, corp_map = load_mapped_data()

def format_table(dataframe, columns):
    f_dict = {col: "{:,.0f}" for col in columns}
    for c in dataframe.columns:
        if 'Rank' in c or c == 'Lvl' or c == 'Weeks':
            f_dict[c] = "{:.0f}"
    return dataframe.style.format(f_dict)

# --- 4. APP DASHBOARD ---
if not df.empty:
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    full_corp_history = df[df['Corp Name'] == selected_corp_name]
    active_df = full_corp_history[full_corp_history['Status'].astype(str).str.contains("Active", case=False, na=False)].copy()
    
    if not full_corp_history.empty:
        tabs = st.tabs(["🏠 Overview", "📈 Weekly Gains", "🗓️ Monthly", "👑 Hall of Fame", "🔥 Streaks", "👤 Profiles", "🔑 Admin"])

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
            st.dataframe(format_table(latest_df[['Player Name', 'Lvl', 'CV', 'DC']], ['Lvl', 'CV', 'DC']), hide_index=True, use_container_width=True)

        # TAB 1: WEEKLY GAINS
        with tabs[1]:
            all_weeks = sorted(active_df['Date'].unique(), reverse=True)
            sel_week_str = st.selectbox("Select Week:", [d.strftime("%Y-%m-%d") for d in all_weeks], key="weekly_sel")
            week_data = active_df[active_df['Date'] == pd.to_datetime(sel_week_str)].copy()
            if not week_data.empty:
                week_data['Lvl Rank'] = week_data['Lvl Gain'].rank(ascending=False, method='min')
                week_data['CV Rank'] = week_data['CV Gain'].rank(ascending=False, method='min')
                week_data['DC Rank'] = week_data['DC Gain'].rank(ascending=False, method='min')
                st.markdown('<div class="section-header">🏅 Weekly Performance Awards</div>', unsafe_allow_html=True)
                a1, a2 = st.columns(2)
                lvl_cut = week_data['Lvl'].quantile(0.35)
                rookies = week_data[week_data['Lvl'] <= lvl_cut]
                if not rookies.empty:
                    rw = rookies.sort_values('DC Gain', ascending=False).iloc[0]
                    a1.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🐣 Rookie of the Week</h3><h1>{rw["Player Name"]}</h1><p>Top DC among players ≤ Lvl {int(lvl_cut)}</p></div>', unsafe_allow_html=True)
                week_data['RS'] = week_data['Lvl Rank'] + week_data['CV Rank'] + week_data['DC Rank']
                rsw = week_data.sort_values(['RS', 'DC Gain'], ascending=[True, False]).iloc[0]
                a2.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🚀 Rising Star</h3><h1>{rsw["Player Name"]}</h1><p>Best combined domain ranking</p></div>', unsafe_allow_html=True)
                w1, w2, w3 = st.columns(3)
                w1.dataframe(format_table(week_data[['Lvl Rank', 'Player Name', 'Lvl Gain']].sort_values('Lvl Rank'), ['Lvl Gain']), hide_index=True)
                w2.dataframe(format_table(week_data[['CV Rank', 'Player Name', 'CV Gain']].sort_values('CV Rank'), ['CV Gain']), hide_index=True)
                w3.dataframe(format_table(week_data[['DC Rank', 'Player Name', 'DC Gain']].sort_values('DC Rank'), ['DC Gain']), hide_index=True)

        # TAB 2: MONTHLY LEADERBOARDS
        with tabs[2]:
            st.markdown('<div class="section-header">🗓️ Monthly Performance & Awards</div>', unsafe_allow_html=True)
            active_df['Month_Key'] = active_df['Date'].dt.to_period('M')
            month_options = sorted(active_df['Month_Key'].unique(), reverse=True)
            sel_month_key = st.selectbox("Select Month:", month_options, format_func=lambda x: x.strftime('%B %Y'))
            m_data = active_df[active_df['Month_Key'] == sel_month_key].copy()
            
            # Week Progress Logic
            year, month = sel_month_key.year, sel_month_key.month
            total_mondays = len([1 for i in calendar.monthcalendar(year, month) if i[0] != 0])
            weeks_recorded = m_data['Date'].nunique()
            is_month_complete = weeks_recorded >= total_mondays
            st.write(f"**Month Progress:** {weeks_recorded} / {total_mondays} Weeks Recorded")

            if not m_data.empty:
                m_totals = m_data.groupby('Player Name').agg({'Lvl Gain':'sum','CV Gain':'sum','DC Gain':'sum','Lvl':'min'}).reset_index()
                if is_month_complete:
                    st.markdown('<div class="section-header">🏆 Monthly Award Winners</div>', unsafe_allow_html=True)
                    ac1, ac2, ac3 = st.columns(3)
                    sr = m_totals.sort_values('Lvl Gain', ascending=False).iloc[0]
                    en = m_totals.sort_values('CV Gain', ascending=False).iloc[0]
                    mvp = m_totals.sort_values('DC Gain', ascending=False).iloc[0]
                    ac1.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">👟 Speed Runner</h3><h1>{sr["Player Name"]}</h1><p>+{int(sr["Lvl Gain"])} Levels</p></div>', unsafe_allow_html=True)
                    ac2.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🏢 Entrepreneurship</h3><h1>{en["Player Name"]}</h1><p>+${int(en["CV Gain"]):,}M CV</p></div>', unsafe_allow_html=True)
                    ac3.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">⭐ MVP</h3><h1>{mvp["Player Name"]}</h1><p>{int(mvp["DC Gain"]):,} Donations</p></div>', unsafe_allow_html=True)
                    
                    # Rookie of the Month Logic
                    f_date = m_data['Date'].min()
                    f_players = active_df[active_df['Date'] == f_date]
                    m_threshold = f_players['Lvl'].quantile(0.35)
                    m_rookies = m_totals[m_totals['Lvl'] <= m_threshold]
                    if not m_rookies.empty:
                        rotm = m_rookies.sort_values('DC Gain', ascending=False).iloc[0]
                        st.markdown(f'<div class="award-card" style="border-color:#00ffff;"><h3 style="color:#00ffff;">🐣 Rookie of the Month</h3><h1>{rotm["Player Name"]}</h1><p>Starting Lvl ≤ {int(m_threshold)}</p></div>', unsafe_allow_html=True)
                else: st.info("💡 Monthly awards will be revealed once the month is complete.")
                
                m_totals['Lvl Rank'] = m_totals['Lvl Gain'].rank(ascending=False, method='min')
                m_totals['CV Rank'] = m_totals['CV Gain'].rank(ascending=False, method='min')
                m_totals['DC Rank'] = m_totals['DC Gain'].rank(ascending=False, method='min')
                m_col1, m_col2, m_col3 = st.columns(3)
                m_col1.dataframe(format_table(m_totals[['Lvl Rank', 'Player Name', 'Lvl Gain']].sort_values('Lvl Rank'), ['Lvl Gain']), hide_index=True)
                m_col2.dataframe(format_table(m_totals[['CV Rank', 'Player Name', 'CV Gain']].sort_values('CV Rank'), ['CV Gain']), hide_index=True)
                m_col3.dataframe(format_table(m_totals[['DC Rank', 'Player Name', 'DC Gain']].sort_values('DC Rank'), ['DC Gain']), hide_index=True)

        # TAB 3: HALL OF FAME
        with tabs[3]:
            st.markdown('<div class="section-header">👑 Lifetime Growth (Active Members)</div>', unsafe_allow_html=True)
            h1, h2, h3 = st.columns(3)
            hof = active_df.groupby('Player Name')[['Lvl Gain', 'CV Gain', 'DC Gain']].sum().reset_index()
            h1.dataframe(format_table(hof[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False), ['Lvl Gain']), hide_index=True)
            h2.dataframe(format_table(hof[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False), ['CV Gain']), hide_index=True)
            h3.dataframe(format_table(hof[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False), ['DC Gain']), hide_index=True)

        # TAB 4: STREAKS
        with tabs[4]:
            st.markdown('<div class="section-header">🔥 Participation Streaks</div>', unsafe_allow_html=True)
            d_wks = sorted(active_df['Date'].unique(), reverse=True)
            s_list = []
            for uid in active_df['UID'].unique():
                p_dates = set(active_df[active_df['UID'] == uid]['Date'])
                c = 0
                for w in d_wks:
                    if w in p_dates: c += 1
                    else: break
                s_list.append({"Player Name": active_df[active_df['UID']==uid]['Player Name'].iloc[0], "Weeks": c})
            st.dataframe(format_table(pd.DataFrame(s_list).sort_values("Weeks", ascending=False), ["Weeks"]), hide_index=True)

        # TAB 5: PROFILES
        with tabs[5]:
            p_status = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']].sort_values(['Status', 'Player Name'])
            sel_p = st.selectbox("Search Member:", p_status['Player Name'].tolist(), key="p_sel")
            p_hist = full_corp_history[full_corp_history['Player Name'] == sel_p].sort_values('Date')
            all_d = pd.date_range(start=p_hist['Date'].min(), end=p_hist['Date'].max(), freq='W-MON')
            p_hist_f = pd.DataFrame({'Date': all_d}).merge(p_hist, on='Date', how='left')
            st.plotly_chart(px.line(p_hist_f, x='Date', y='Lvl Gain', title="Progression").update_traces(connectgaps=False))
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Status", p_hist['Status'].iloc[-1])
            m2.metric("Total Lvl Gain", f"+{int(p_hist['Lvl Gain'].sum()):,}")
            m3.metric("Avg Weekly DC", f"+{int(p_hist[p_hist['DC Gain']>0]['DC Gain'].mean() if not p_hist[p_hist['DC Gain']>0].empty else 0):,}")
            m4.metric("Total DC", f"{int(p_hist['DC Gain'].sum()):,}")

        # TAB 6: ADMIN
        with tabs[6]:
            if st.text_input("Password:", type="password") == st.secrets.get("admin_password", "rcttaddict"):
                with st.form("add_log"):
                    f1, f2 = st.columns(2)
                    d, u, c = f1.date_input("Date", date.today()), f1.text_input("UID"), f2.text_input("Corp ID", "CORP_001")
                    l, cv, dc = f2.number_input("Lvl", 1, 999, 100), f1.number_input("CV (M)", 0, 1000000, 1000), f2.number_input("Donations", 0, 1000000, 0)
                    if st.form_submit_button("Commit"):
                        stats_ws.append_row([str(d), c, u, int(l), int(cv), int(dc)])
                        st.cache_data.clear()
                        st.rerun()
    else: st.warning("No data found for this selection.")
else: st.info("Awaiting connection to database...")
