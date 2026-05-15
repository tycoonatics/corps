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

# --- 2. CSS STYLING (Dark Mode & Mobile Friendly) ---
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

        # SPIKE PROTECTION: Detect re-entry gaps
        stats_df['Days_Gap'] = stats_df.groupby('UID')['Date'].diff().dt.days
        
        for col in ['Lvl', 'CV', 'DC']:
            stats_df[f'{col}_Raw_Diff'] = stats_df.groupby('UID')[col].diff()
            
            def sanitize_gains(row, column):
                diff = row[f'{column}_Raw_Diff']
                gap = row['Days_Gap']
                # If first entry, negative, gap > 10 days, or impossible jump (>150k DC)
                if pd.isna(diff) or diff < 0 or gap > 10:
                    return 0
                if column == 'DC' and diff > 150000:
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

        # TAB 1: OVERVIEW
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

        # TAB 2: WEEKLY GAINS
        with tabs[1]:
            all_weeks = sorted(active_df['Date'].unique(), reverse=True)
            sel_week = st.selectbox("Select Week:", [d.strftime("%Y-%m-%d") for d in all_weeks])
            week_data = active_df[active_df['Date'] == pd.to_datetime(sel_week)]
            w1, w2, w3 = st.columns(3)
            w1.subheader("📈 Lvl Gain")
            w1.dataframe(format_table(week_data[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False), ['Lvl Gain']), hide_index=True, use_container_width=True)
            w2.subheader("💰 CV Gain")
            w2.dataframe(format_table(week_data[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False), ['CV Gain']), hide_index=True, use_container_width=True)
            w3.subheader("💫 DC Gain")
            w3.dataframe(format_table(week_data[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False), ['DC Gain']), hide_index=True, use_container_width=True)

        # TAB 3: HALL OF FAME
        with tabs[2]:
            st.markdown('<div class="section-header">👑 Lifetime Growth (Active Members)</div>', unsafe_allow_html=True)
            h1, h2, h3 = st.columns(3)
            hof_df = active_df.groupby('Player Name')[['Lvl Gain', 'CV Gain', 'DC Gain']].sum().reset_index()
            h1.subheader("🏆 Total Lvl Gain")
            h1.dataframe(format_table(hof_df[['Player Name', 'Lvl Gain']].sort_values('Lvl Gain', ascending=False), ['Lvl Gain']), hide_index=True, use_container_width=True)
            h2.subheader("💰 Total CV Gain")
            h2.dataframe(format_table(hof_df[['Player Name', 'CV Gain']].sort_values('CV Gain', ascending=False), ['CV Gain']), hide_index=True, use_container_width=True)
            h3.subheader("💫 Total DC")
            h3.dataframe(format_table(hof_df[['Player Name', 'DC Gain']].sort_values('DC Gain', ascending=False), ['DC Gain']), hide_index=True, use_container_width=True)

        # TAB 4: STREAKS
        with tabs[3]:
            distinct_weeks = sorted(active_df['Date'].unique(), reverse=True)
            streak_list = []
            for uid in active_df['UID'].unique():
                p_dates = set(active_df[active_df['UID'] == uid]['Date'])
                c = 0
                for w in distinct_weeks:
                    if w in p_dates: c += 1
                    else: break
                streak_list.append({"Player Name": active_df[active_df['UID']==uid]['Player Name'].iloc[0], "Weeks": c})
            st.dataframe(format_table(pd.DataFrame(streak_list).sort_values("Weeks", ascending=False), ["Weeks"]), hide_index=True, use_container_width=True)

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
            active_weeks = p_history[p_history['DC Gain'] > 0]
            avg_dc_val = active_weeks['DC Gain'].mean() if not active_weeks.empty else 0
            
            m1.metric("Status", p_history['Status'].iloc[-1])
            m2.metric("Total Lvl Gain", f"+{int(p_history['Lvl Gain'].sum()):,}")
            m3.metric("Avg Weekly DC", f"+{int(avg_dc_val):,}")
            m4.metric("Total DC Contribution", f"{int(p_history['DC Gain'].sum()):,}")

        # TAB 6: ADMIN
        with tabs[5]:
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
        st.warning("No data found for this corporation.")
else:
    st.info("System Ready. Please connect your spreadsheet.")
