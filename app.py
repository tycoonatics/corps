import calendar

# --- UPDATED MONTHLY TAB LOGIC ---
with tabs[2]:
    st.markdown('<div class="section-header">🗓️ Monthly Performance & Awards</div>', unsafe_allow_html=True)
    
    # 1. Identify Month Context
    active_df['Month_Key'] = active_df['Date'].dt.to_period('M')
    month_options = sorted(active_df['Month_Key'].unique(), reverse=True)
    sel_month_key = st.selectbox("Select Month:", month_options, format_func=lambda x: x.strftime('%B %Y'))
    
    # Filter data for selected month
    m_data = active_df[active_df['Month_Key'] == sel_month_key].copy()
    
    # 2. Week Counter (Current vs Total Mondays in Month)
    year, month = sel_month_key.year, sel_month_key.month
    total_mondays = len([1 for i in calendar.monthcalendar(year, month) if i[0] != 0]) # Count Mondays in cal
    weeks_recorded = m_data['Date'].nunique()
    is_month_complete = weeks_recorded >= total_mondays
    
    st.write(f"**Month Progress:** {weeks_recorded} / {total_mondays} Weeks Recorded")

    if not m_data.empty:
        # Calculate Monthly Aggregates
        monthly_totals = m_data.groupby('Player Name').agg({
            'Lvl Gain': 'sum',
            'CV Gain': 'sum',
            'DC Gain': 'sum',
            'Lvl': 'min',  # Level at the start of their month
            'Date': 'min'  # First appearance this month
        }).reset_index()

        # 3. Monthly Awards (Only if month is complete)
        if is_month_complete:
            st.markdown('<div class="section-header">🏆 Monthly Award Winners</div>', unsafe_allow_html=True)
            ac1, ac2, ac3 = st.columns(3)
            
            # Speed Runner (Lvl), Entrepreneur (CV), MVP (DC)
            sr_winner = monthly_totals.sort_values('Lvl Gain', ascending=False).iloc[0]
            en_winner = monthly_totals.sort_values('CV Gain', ascending=False).iloc[0]
            mvp_winner = monthly_totals.sort_values('DC Gain', ascending=False).iloc[0]
            
            ac1.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">👟 Speed Runner</h3><h1>{sr_winner["Player Name"]}</h1><p>+{int(sr_winner["Lvl Gain"])} Levels</p></div>', unsafe_allow_html=True)
            ac2.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">🏢 Entrepreneur</h3><h1>{en_winner["Player Name"]}</h1><p>+${int(en_winner["CV Gain"]):,}M CV</p></div>', unsafe_allow_html=True)
            ac3.markdown(f'<div class="award-card"><h3 style="color:#ffd700;">⭐ MVP</h3><h1>{mvp_winner["Player Name"]}</h1><p>{int(mvp_winner["DC Gain"]):,} Donations</p></div>', unsafe_allow_html=True)

            # 4. Rookie of the Month Logic
            # Find the global Lvl threshold from the first week of the month
            first_week_date = m_data['Date'].min()
            first_week_players = active_df[active_df['Date'] == first_week_date]
            rookie_lvl_threshold = first_week_players['Lvl'].quantile(0.35)

            # Qualifying players: 
            # 1. Level at month-start <= threshold OR 
            # 2. Joined mid-month and first recorded level <= threshold
            qualifying_rookies = monthly_totals[monthly_totals['Lvl'] <= rookie_lvl_threshold]

            if not qualifying_rookies.empty:
                rotm_winner = qualifying_rookies.sort_values('DC Gain', ascending=False).iloc[0]
                st.markdown(f'''
                    <div class="award-card" style="background: rgba(0, 255, 255, 0.05); border-color: #00ffff;">
                        <h3 style="color:#00ffff;">🐣 Rookie of the Month</h3>
                        <h1>{rotm_winner["Player Name"]}</h1>
                        <p>Qualifying Level: ≤ {int(rookie_lvl_threshold)} | Monthly DC: {int(rotm_winner["DC Gain"]):,}</p>
                    </div>
                ''', unsafe_allow_html=True)
        else:
            st.info("💡 Monthly awards will be revealed once all weeks for this month are recorded.")

        # 5. Monthly Leaderboards
        st.markdown('<div class="section-header">📊 Monthly Rankings</div>', unsafe_allow_html=True)
        monthly_totals['Lvl Rank'] = monthly_totals['Lvl Gain'].rank(ascending=False, method='min')
        monthly_totals['CV Rank'] = monthly_totals['CV Gain'].rank(ascending=False, method='min')
        monthly_totals['DC Rank'] = monthly_totals['DC Gain'].rank(ascending=False, method='min')
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.subheader("📈 Lvl Gain")
            st.dataframe(format_table(monthly_totals[['Lvl Rank', 'Player Name', 'Lvl Gain']].sort_values('Lvl Rank'), ['Lvl Gain']), hide_index=True, use_container_width=True)
        with m_col2:
            st.subheader("💰 CV Gain")
            st.dataframe(format_table(monthly_totals[['CV Rank', 'Player Name', 'CV Gain']].sort_values('CV Rank'), ['CV Gain']), hide_index=True, use_container_width=True)
        with m_col3:
            st.subheader("💫 DC Gain")
            st.dataframe(format_table(monthly_totals[['DC Rank', 'Player Name', 'DC Gain']].sort_values('DC Rank'), ['DC Gain']), hide_index=True, use_container_width=True)
