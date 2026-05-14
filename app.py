import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Set up widescreen page layout
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# Custom CSS styling to inject a clean dashboard look
st.markdown("""
    <style>
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
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏆 RCTT Corporation Hub Network")

# 1. Connect to Google Sheets using direct vanilla API authentication
@st.cache_data(ttl=5)
def load_data_from_sheets():
    try:
        # Extract the credentials dictionary directly from secrets
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        sheet_url = creds_dict["spreadsheet"]
        
        # Authenticate securely with Google APIs
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Open workbook and fetch rows
        workbook = client.open_by_url(sheet_url)
        worksheet = workbook.worksheet("Corporation_Stats")
        records = worksheet.get_all_records()
        
        # Convert to DataFrame
        raw_df = pd.DataFrame(records)
        return raw_df, worksheet, sheet_url
    except Exception as e:
        st.error(f"API Authentication Failed: {e}")
        return pd.DataFrame(), None, None

# Load dataset
df, target_worksheet, active_sheet_url = load_data_from_sheets()

if not df.empty:
    df['Date'] = pd.to_datetime(df['Date'])
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(0).astype(int)
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0).astype(int)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0).astype(int)

    # Main Dropdown Selector
    available_corps = sorted(df['Corp Name'].unique())
    selected_corp = st.selectbox("Choose Active Corporation:", available_corps)
    
    corp_df = df[df['Corp Name'] == selected_corp]
    
    if not corp_df.empty:
        latest_date = corp_df['Date'].max()
        latest_df = corp_df[corp_df['Date'] == latest_date]
        
        # ==========================================
        # TOP ROW: HEADLINE METRICS (Weekly & Monthly Banners)
        # ==========================================
        total_value = latest_df['Company Value'].sum()
        total_donations = latest_df['Donation Count'].sum()
        member_count = latest_df['Player Name'].nunique()
        
        # Calculate Monthly Gains (Current Date vs 30 Days Ago)
        month_ago_date = latest_date - timedelta(days=30)
        historical_corp_df = corp_df[corp_df['Date'] <= month_ago_date]
        
        if not historical_corp_df.empty:
            oldest_recorded_date = historical_corp_df['Date'].max()
            past_df = corp_df[corp_df['Date'] == oldest_recorded_date]
            
            monthly_cv_delta = total_value - past_df['Company Value'].sum()
            monthly_dc_delta = total_donations - past_df['Donation Count'].sum()
        else:
            monthly_cv_delta = 0
            monthly_dc_delta = 0
            
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Active Corp", selected_corp)
        m_col2.metric("Roster", f"{member_count}/20 Members")
        m_col3.metric("Total Value", f"${total_value:,.0f} M", delta=f"{monthly_cv_delta:+,} M Month")
        m_col4.metric("Weekly Donations", f"{total_donations:,} DC", delta=f"{monthly_dc_delta:+,} DC Month")
        
        # ==========================================
        # ROW 2: WEEKLY PERFORMANCE LEADERBOARDS
        # ==========================================
        st.markdown('<div class="section-header">📊 Weekly Performance Leaderboards</div>', unsafe_allow_html=True)
        lead_col1, lead_col2, lead_col3 = st.columns(3)
        
        with lead_col1:
            st.subheader("🔺 Level Standings")
            lvl_df = latest_df[["Player Name", "Player Level"]].sort_values(by="Player Level", ascending=False).reset_index(drop=True)
            lvl_df.index += 1
            st.dataframe(lvl_df, use_container_width=True)
            
        with lead_col2:
            st.subheader("💰 Company Value")
            cv_df = latest_df[["Player Name", "Company Value"]].sort_values(by="Company Value", ascending=False).reset_index(drop=True)
            cv_df.index += 1
            st.dataframe(cv_df, use_container_width=True, column_config={"Company Value": st.column_config.NumberColumn(format="%,d M")})
            
        with lead_col3:
            st.subheader("🟢 Donation Count (DC)")
            dc_df = latest_df[["Player Name", "Donation Count"]].sort_values(by="Donation Count", ascending=False).reset_index(drop=True)
            dc_df.index += 1
            st.dataframe(dc_df, use_container_width=True, column_config={"Donation Count": st.column_config.NumberColumn(format="%,d")})
            
        # ==========================================
        # ROW 3: MONTHLY PROGRESS LEADERBOARDS 
        # ==========================================
        st.markdown('<div class="section-header">📅 Monthly Gains & Growth Leaderboards (Last 30 Days)</div>', unsafe_allow_html=True)
        
        if not historical_corp_df.empty:
            base_df = corp_df[corp_df['Date'] == oldest_recorded_date][['Player Name', 'Player Level', 'Company Value']]
            base_df.columns = ['Player Name', 'Base Level', 'Base CV']
            
            monthly_merge = pd.merge(latest_df, base_df, on='Player Name', how='left')
            monthly_merge['Base Level'] = monthly_merge['Base Level'].fillna(monthly_merge['Player Level'])
            monthly_merge['Base CV'] = monthly_merge['Base CV'].fillna(monthly_merge['Company Value'])
            
            monthly_merge['Δ Lvl'] = monthly_merge['Player Level'] - monthly_merge['Base Level']
            monthly_merge['Δ CV'] = monthly_merge['Company Value'] - monthly_merge['Base CV']
            
            m_lead1, m_lead2, m_lead3 = st.columns(3)
            
            with m_lead1:
                st.subheader("🔺 Monthly Δ Level")
                m_lvl = monthly_merge[["Player Name", "Δ Lvl"]].sort_values(by="Δ Lvl", ascending=False).reset_index(drop=True)
                m_lvl.index += 1
                st.dataframe(m_lvl, use_container_width=True, column_config={"Δ Lvl": st.column_config.NumberColumn(format="+%,d")})
                
            with m_lead2:
                st.subheader("💰 Monthly Δ CV")
                m_cv = monthly_merge[["Player Name", "Δ CV"]].sort_values(by="Δ CV", ascending=False).reset_index(drop=True)
                m_cv.index += 1
                st.dataframe(m_cv, use_container_width=True, column_config={"Δ CV": st.column_config.NumberColumn(format="+%,d M")})
                
            with m_lead3:
                st.subheader("🟢 Monthly Accumulated DC")
                recent_dc = corp_df[corp_df['Date'] > month_ago_date].groupby('Player Name')['Donation Count'].sum().reset_index()
                recent_dc.columns = ['Player Name', 'Total Monthly DC']
                m_dc = recent_dc.sort_values(by="Total Monthly DC", ascending=False).reset_index(drop=True)
                m_dc.index += 1
                st.dataframe(m_dc, use_container_width=True, column_config={"Total Monthly DC": st.column_config.NumberColumn(format="%,d")})
        else:
            st.info("Log at least two weeks of data to generate monthly delta calculations.")

        # ==========================================
        # ROW 4: ALL-TIME OVERALL LEADERBOARDS
        # ==========================================
        st.markdown('<div class="section-header">👑 All-Time Overall Hall of Fame Standings</div>', unsafe_allow_html=True)
        all_time_col1, all_time_col2, all_time_col3 = st.columns(3)
        
        with all_time_col1:
            st.subheader("🏆 Peak Player Level")
            overall_lvl = corp_df.groupby('Player Name')['Player Level'].max().reset_index()
            overall_lvl = overall_lvl.sort_values(by='Player Level', ascending=False).reset_index(drop=True)
            overall_lvl.index += 1
            st.dataframe(overall_lvl, use_container_width=True)
            
        with all_time_col2:
            st.subheader("👑 Highest Company Value")
            overall_cv = corp_df.groupby('Player Name')['Company Value'].max().reset_index()
            overall_cv = overall_cv.sort_values(by='Company Value', ascending=False).reset_index(drop=True)
            overall_cv.index += 1
            st.dataframe(overall_cv, use_container_width=True, column_config={"Company Value": st.column_config.NumberColumn(format="%,d M")})
            
        with all_time_col3:
            st.subheader("💫 Lifetime Cumulative Donations")
            overall_dc = corp_df.groupby('Player Name')['Donation Count'].sum().reset_index()
            overall_dc.columns = ['Player Name', 'Lifetime Total DC']
            overall_dc = overall_dc.sort_values(by='Lifetime Total DC', ascending=False).reset_index(drop=True)
            overall_dc.index += 1
            st.dataframe(overall_dc, use_container_width=True, column_config={"Lifetime Total DC": st.column_config.NumberColumn(format="%,d")})

        # ==========================================
        # ROW 5: STREAKS HIGHLIGHT PANEL
        # ==========================================
        st.markdown('<div class="section-header">🔥 Active Corporation Streaks (Consecutive Weeks)</div>', unsafe_allow_html=True)
        
        streak_data = []
        all_players_list = corp_df['Player Name'].unique()
        distinct_weeks = sorted(corp_df['Date'].unique(), reverse=True)
        
        for player in all_players_list:
            player_logs = corp_df[corp_df['Player Name'] == player]
            logged_dates = set(player_logs['Date'])
            
            weeks_streak = 0
            for week in distinct_weeks:
                if week in logged_dates:
                    weeks_streak += 1
                else:
                    break
                    
            donation_streak = 0
            for week in distinct_weeks:
                if week in logged_dates:
                    week_dc = player_logs[player_logs['Date'] == week]['Donation Count'].values[0]
                    if week_dc > 0:
                        donation_streak += 1
                    else:
                        break
                else:
                    break
                    
            streak_data.append({
                "Player Name": player,
                "Weeks in Corp (Streak)": f"🔥 {weeks_streak} Wks",
                "Donation Streak (Active)": f"💚 {donation_streak} Wks" if donation_streak > 0 else "---"
            })
            
        streak_df = pd.DataFrame(streak_data).sort_values(by="Weeks in Corp (Streak)", ascending=False).reset_index(drop=True)
        streak_df.index += 1
        st.dataframe(streak_df, use_container_width=True)

        # ==========================================
        # ROW 6: CHARTS & HISTORICAL TRENDS
        # ==========================================
        st.markdown('<div class="section-header">📈 Performance History & Trends</div>', unsafe_allow_html=True)
        chart_col1, chart_col2 = st.columns(2)
        corp_timeline = corp_df.groupby('Date').agg({'Donation Count': 'sum', 'Company Value': 'sum'}).reset_index()
        
        with chart_col1:
            st.markdown("**Last Week's Individual Donation Distribution**")
            st.bar_chart(latest_df.set_index('Player Name')['Donation Count'])
            
        with chart_col2:
            st.markdown("**Corp Donation Volume (6-Week View)**")
            st.line_chart(corp_timeline.set_index('Date')['Donation Count'])
            
        st.divider()
        
        # ==========================================
        # ROW 7: ENTRY FORM PANEL (Admin Tool)
        # ==========================================
        st.markdown('<div class="section-header">🔑 Corporation Administration Log Panel</div>', unsafe_allow_html=True)
        if target_worksheet is not None:
            with st.form("data_entry_form", clear_on_submit=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                input_date = f_col1.date_input("Log Date:", date.today())
                input_corp = f_col1.text_input("Corporation Name:", value=selected_corp)
                input_name = f_col2.text_input("Player Name:")
                input_level = f_col2.number_input("Player Level:", min_value=1, max_value=150, value=50)
                input_value = f_col3.number_input("Company Value (Coins):", min_value=0, value=1000000)
                input_donations = f_col3.number_input("Weekly Donation Count:", min_value=0, value=0)
                
                submit_button = st.form_submit_button("Commit Weekly Stats to Database")
                
                if submit_button:
                    if not input_name.strip() or not input_corp.strip():
                        st.error("Error: Key data fields cannot be blank.")
                    else:
                        # Append directly using gspread mechanics
                        new_row = [
                            str(input_date),
                            input_corp.strip(),
                            input_name.strip(),
                            int(input_level),
                            int(input_value),
                            int(input_donations)
                        ]
                        target_worksheet.append_row(new_row)
                        st.success(f"Appended records for {input_name} successfully!")
                        st.cache_data.clear()
                        st.timer(1)
                        st.rerun()
        else:
            st.warning("Data submission unavailable due to read-only state.")
else:
    st.info("The database appears empty or is structured incorrectly. Verify column headers match exactly: 'Date', 'Corp Name', 'Player Name', 'Player Level', 'Company Value', 'Donation Count'")
