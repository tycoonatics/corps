import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# --- 2. CUSTOM UI STYLING (Knowledge Hub Branding) ---
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #ff8c00, #ff0080);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-family: 'Arial Black', sans-serif;
        font-size: 3rem;
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
    /* Hide Streamlit Branding for Stealth Mode */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT KNOWLEDGE HUB 🏆</div>', unsafe_allow_html=True)

# --- 3. DATABASE CONNECTION & MAPPING LOGIC ---
@st.cache_data(ttl=5)
def load_mapped_data():
    try:
        s = st.secrets["connections"]["gsheets"]
        decoded_creds = base64.b64decode(s["encoded_creds"]).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        # Open the specific spreadsheet
        sh = gc.open("RCTT_Hub_DB")
        
        # Load Reference Data (Dictionary)
        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = ref_df[ref_df['ID_Type'] == 'Player'].set_index('ID_Value')['Display_Name'].to_dict()
        corp_map = ref_df[ref_df['ID_Type'] == 'Corp'].set_index('ID_Value')['Display_Name'].to_dict()
        
        # Load Raw Statistics
        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())
        
        # Data Cleaning & Mapping
        stats_df['Date'] = pd.to_datetime(stats_df['Date'])
        stats_df['Player Name'] = stats_df['UID'].map(player_map).fillna(stats_df['UID'])
        stats_df['Corp Name'] = stats_df['Corp_ID'].map(corp_map).fillna(stats_df['Corp_ID'])
        
        # Ensure numeric types for calculations
        num_cols = ['Level', 'Value', 'Donations']
        for col in num_cols:
            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce').fillna(0)
            
        return stats_df, raw_stats_ws, player_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection or Mapping Failed: {e}")
        return pd.DataFrame(), None, {}, {}

df, stats_ws, player_map, corp_map = load_mapped_data()

# --- 4. APP DASHBOARD ---
if not df.empty:
    # Sidebar Global Filters
    st.sidebar.header("Global Controls")
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp_name = st.sidebar.selectbox("Active Corporation:", available_corps)
    
    # Filter primary dataframe
    corp_df = df[df['Corp Name'] == selected_corp_name].sort_values('Date', ascending=False)
    latest_date = corp_df['Date'].max()
    latest_df = corp_df[corp_df['Date'] == latest_date]

    # Organize Hub into Tabs
    tab_overview, tab_leaderboards, tab_profiles, tab_admin = st.tabs([
        "🏠 Overview", "📊 Leaderboards", "👤 Member Profiles", "🔑 Admin Entry"
    ])

    # --- TAB 1: OVERVIEW ---
    with tab_overview:
        st.markdown(f'<div class="section-header">📈 {selected_corp_name} Summary ({latest_date.date()})</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Roster", f"{len(latest_df)}/20")
        m2.metric("Net Worth", f"${latest_df['Value'].sum():,.0f}M")
        m3.metric("Total Donations", f"{latest_df['Donations'].sum():,.0f}")
        m4.metric("Avg Level", f"{latest_df['Level'].mean():.1f}")
        
        st.write("### 🔥 Current Standings")
        st.dataframe(latest_df[['Player Name', 'Level', 'Value', 'Donations']], hide_index=True, use_container_width=True)

    # --- TAB 2: LEADERBOARDS & STREAKS ---
    with tab_leaderboards:
        st.markdown('<div class="section-header">🏅 Weekly Performance</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("💰 Top Company Value")
            st.dataframe(latest_df[['Player Name', 'Value']].sort_values('Value', ascending=False), hide_index=True, use_container_width=True)
        with col_b:
            st.subheader("🟢 Weekly Donation Leaders")
            st.dataframe(latest_df[['Player Name', 'Donations']].sort_values('Donations', ascending=False), hide_index=True, use_container_width=True)

        st.markdown('<div class="section-header">🔥 Participation Streaks</div>', unsafe_allow_html=True)
        # Logic to calculate consecutive weeks logged
        streak_list = []
        all_uids = corp_df['UID'].unique()
        distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
        
        for uid in all_uids:
            p_logs = corp_df[corp_df['UID'] == uid]
            p_name = p_logs['Player Name'].iloc[0]
            logged_dates = set(p_logs['Date'])
            
            count = 0
            for w in distinct_weeks:
                if w in logged_dates: count += 1
                else: break
            streak_list.append({"Player": p_name, "Streak": f"🔥 {count} Weeks"})
            
        st.table(pd.DataFrame(streak_list).sort_values('Streak', ascending=False).head(10))

    # --- TAB 3: MEMBER PROFILES ---
    with tab_profiles:
        st.markdown('<div class="section-header">👤 Historical Player Profile</div>', unsafe_allow_html=True)
        selected_player = st.selectbox("Select Member:", sorted(corp_df['Player Name'].unique()))
        
        p_history = corp_df[corp_df['Player Name'] == selected_player].sort_values('Date')
        
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.metric("All-Time Peak Level", p_history['Level'].max())
            st.metric("Lifetime Donation Vol", f"{p_history['Donations'].sum():,.0f}")
            st.metric("Highest Value Hit", f"${p_history['Value'].max():,.0f}M")
        
        with c_right:
            fig = px.line(p_history, x='Date', y='Value', title='Company Value Progression', markers=True)
            st.plotly_chart(fig, use_container_width=True)

    # --- TAB 4: ADMIN ENTRY ---
    with tab_admin:
        st.markdown('<div class="section-header">🔑 Log New Entry</div>', unsafe_allow_html=True)
        with st.form("data_entry", clear_on_submit=True):
            f1, f2 = st.columns(2)
            in_date = f1.date_input("Date", date.today())
            in_uid = f1.text_input("Player UID (Must match Reference Data)")
            
            # Show name preview to avoid errors
            if in_uid in player_map:
                f1.success(f"Recognized: **{player_map[in_uid]}**")
            elif in_uid:
                f1.warning("New UID detected. Ensure you add this to Reference Data sheet.")
                
            in_corp_id = f2.text_input("Corp ID", value=latest_df['Corp_ID'].iloc[0] if not latest_df.empty else "")
            in_lvl = f2.number_input("Current Level", 1, 999, 50)
            in_val = f1.number_input("Company Value (M)", 0, 1000000, 100)
            in_don = f2.number_input("Donations This Week", 0, 100000, 0)
            
            if st.form_submit_button("Commit to Spreadsheet"):
                if in_uid and in_corp_id:
                    # Append exactly as the columns are named in your sheet
                    new_row = [str(in_date), in_corp_id, in_uid, in_lvl, in_val, in_don]
                    stats_ws.append_row(new_row)
                    st.success("Entry recorded! Refreshing...")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("UID and Corp ID are required.")
else:
    st.info("The Hub is ready. Please add your first entries in the 'Admin Entry' tab or directly in the 'Corporation_Stats' sheet.")
