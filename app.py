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

        # Gains Calculation with Spike Protection
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
        if any(x in c for x in ['Rank', 'Lvl', 'Weeks', 'Top 3', '1,000+']):
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
                a2.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🚀 Rising Star</h3><h1>{rsw["Player Name"]}</h1></div>', unsafe_allow_html=True)
                w1, w2, w3 = st.columns(3)
                w1.dataframe(format_table(week_data[['Lvl Rank', 'Player Name', 'Lvl Gain']].sort_values('Lvl Rank'), ['Lvl Gain']), hide_index=True)
                w2.dataframe(format_table(week_data[['CV Rank', 'Player Name', 'CV Gain']].sort_values('CV Rank'), ['CV Gain']), hide_index=True)
                w3.dataframe(format_table(week_data[['DC Rank', 'Player Name', 'DC Gain']].sort_values('DC Rank'), ['DC Gain']), hide_index=True)

        # TAB 2: MONTHLY
        with tabs[2]:
            st.markdown('<div class="section-header">🗓️ Monthly Performance & Awards</div>', unsafe_allow_html=True)
            active_df['Month_Key'] = active_df['Date'].dt.to_period('M')
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
                    f_wk = m_data['Date'].min()
                    f_lvl = active_df[active_df['Date'] == f_wk]['Lvl'].quantile(0.35)
                    m_rook = m_totals[m_totals['Lvl'] <= f_lvl].sort_values('DC Gain', ascending=False)
                    if not m_rook.empty:
                        rotm = m_rook.iloc[0]
                        st.markdown(f'<div class="award-card" style="border-color:#00ffff;"><h3 style="color:#00ffff;">🐣 Rookie of the Month</h3><h1>{rotm["Player Name"]}</h1></div>', unsafe_allow_html=True)
                m_totals['Lvl Rank'] = m_totals['Lvl Gain'].rank(ascending=False, method='min')
                m_totals['CV Rank'] = m_totals['CV Gain'].rank(ascending=False, method='min')
                m_totals['DC Rank'] = m_totals['DC Gain'].rank(ascending=False, method='min')
                mc1, mc2, mc3 = st.columns(3)
                mc1.dataframe(format_table(m_totals[['Lvl Rank', 'Player Name', 'Lvl Gain']].sort_values('Lvl Rank'), ['Lvl Gain']), hide_index=True)
                mc2.dataframe(format_table(m_totals[['CV Rank', 'Player Name', 'CV Gain']].sort_values('CV Rank'), ['CV Gain']), hide_index=True)
                mc3.dataframe(format_table(m_totals[['DC Rank', 'Player Name', 'DC Gain']].sort_values('DC Rank'), ['DC Gain']), hide_index=True)

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
            st.markdown('<div class="section-header">🔥 Elite Performance Streaks</div>', unsafe_allow_html=True)
            def get_streak(p_hist, col):
                s = 0
                for val in p_hist.sort_values('Date', ascending=False)[col]:
                    if val: s += 1
                    else: break
                return s
            s_data = active_df.copy()
            s_data['L3'] = s_data.groupby('Date')['Lvl Gain'].rank(ascending=False, method='min') <= 3
            s_data['C3'] = s_data.groupby('Date')['CV Gain'].rank(ascending=False, method='min') <= 3
            s_data['D1K'] = s_data['DC Gain'] >= 1000
            
            # Award logic (simplified for streak scan)
            s_data['is_RS'] = False # Logic can be expanded based on Tab 1
            s_data['is_RotW'] = False 

            final_s = []
            for uid in s_data['UID'].unique():
                p_h = s_data[s_data['UID'] == uid]
                final_s.append({
                    "Player Name": p_h['Player Name'].iloc[0],
                    "Lvl Top 3": get_streak(p_h, 'L3'),
                    "CV Top 3": get_streak(p_h, 'C3'),
                    "1,000+ DC": get_streak(p_h, 'D1K'),
                    "RotW": get_streak(p_h, 'is_RotW'),
                    "Rising Star": get_streak(p_h, 'is_RS')
                })
            st.dataframe(format_table(pd.DataFrame(final_s).sort_values("1,000+ DC", ascending=False), 
                         ["Lvl Top 3", "CV Top 3", "1,000+ DC", "RotW", "Rising Star"]), hide_index=True, use_container_width=True)

        # TAB 5: PROFILES
        with tabs[5]:
            p_status = full_corp_history.drop_duplicates(subset=['Player Name'], keep='last')[['Player Name', 'Status']].sort_values(['Status', 'Player Name'])
            sel_p = st.selectbox("Search Member:", p_status['Player Name'].tolist(), key="p_sel")
            p_hist = full_corp_history[full_corp_history['Player Name'] == sel_p].sort_values('Date')
            st.plotly_chart(px.line(p_hist, x='Date', y='Lvl Gain', markers=True))
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Status", p_hist['Status'].iloc[-1])
            m2.metric("Total Lvl", f"+{int(p_hist['Lvl Gain'].sum()):,}")
            m3.metric("Avg DC", f"{int(p_hist[p_hist['DC Gain']>0]['DC Gain'].mean() if not p_hist[p_hist['DC Gain']>0].empty else 0):,}")
            m4.metric("Total DC", f"{int(p_hist['DC Gain'].sum()):,}")

        # TAB 6: ADMIN
        with tabs[6]:
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
else: st.info("Awaiting connection...")
