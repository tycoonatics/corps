# TAB 1: ALL-TIME LEADERBOARDS
        with tabs[1]:
            st.markdown('<div class="section-header">👑 All-Time Standings (Active Members Only)</div>', unsafe_allow_html=True)
            
            # Extract absolute latest entries first
            latest_snapshots = full_corp_history.sort_values('Date').groupby('Player Name').last().reset_index()
            # Strict verification step: Keep records *only* if their absolute latest status flag is 'Active'
            current_snapshots = latest_snapshots[latest_snapshots['Status'].astype(str).str.contains("Active", case=False, na=False)].copy()
            
            if not current_snapshots.empty:
                # Compute discrete individual ranks
                current_snapshots['L_Rank'] = current_snapshots['Lvl'].rank(ascending=False, method='min')
                current_snapshots['C_Rank'] = current_snapshots['CV'].rank(ascending=False, method='min')
                current_snapshots['D_Rank'] = current_snapshots['DC'].rank(ascending=False, method='min')
                
                # Performance aggregate tracking (Lowest rank sum wins)
                current_snapshots['Rank_Sum'] = current_snapshots['L_Rank'] + current_snapshots['C_Rank'] + current_snapshots['D_Rank']
                current_snapshots['Overall_Rank'] = current_snapshots['Rank_Sum'].rank(ascending=True, method='min')
                
                # Master Overall Leaderboard Display
                st.markdown('<div class="domain-header overall-bg">👑 Master Overall Standings</div>', unsafe_allow_html=True)
                
                # Organize and align rank headers to the left of their metrics
                master_board = current_snapshots[[
                    'Overall_Rank', 'Player Name', 
                    'L_Rank', 'Lvl', 
                    'C_Rank', 'CV', 
                    'D_Rank', 'DC'
                ]].sort_values('Overall_Rank')
                
                master_board.rename(columns={
                    'Overall_Rank': 'Overall Rank', 
                    'L_Rank': 'Lvl Rank', 
                    'C_Rank': 'CV Rank', 
                    'D_Rank': 'DC Rank'
                }, inplace=True)
                
                # Format the numbers first using your existing formatter
                styled_master = format_table(master_board, ['Lvl', 'CV', 'DC'])
                
                # Use st.dataframe configuration to add structural grouping and highlight the Overall Rank column
                st.dataframe(
                    styled_master,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Overall Rank": st.column_config.NumberColumn(
                            "🏅 Overall Rank",
                            help="Highest overall standing based on combined ranks",
                            background_color="rgba(147, 51, 234, 0.2)" # Subtle purple highlight matching your header
                        ),
                        "Player Name": st.column_config.TextColumn("Player Name"),
                        # Group 1: Level
                        "Lvl Rank": st.column_config.NumberColumn("📊 Lvl Rank"),
                        "Lvl": st.column_config.NumberColumn("Lvl    |"), # Visual pipe spacer to separate groups
                        # Group 2: CV
                        "CV Rank": st.column_config.NumberColumn("💰 CV Rank"),
                        "CV": st.column_config.NumberColumn("CV (M)    |"), # Visual pipe spacer to separate groups
                        # Group 3: DC
                        "DC Rank": st.column_config.NumberColumn("🎁 DC Rank"),
                        "DC": st.column_config.NumberColumn("Total DC")
                    }
                )
                
                # Segmented Column Sub-boards
                al_c1, al_c2, al_c3 = st.columns(3)
                with al_c1:
                    st.markdown('<div class="domain-header lvl-bg">📈 All-Time Level (Lvl)</div>', unsafe_allow_html=True)
                    al_lvl = current_snapshots[['L_Rank', 'Player Name', 'Lvl']].sort_values('L_Rank')
                    al_lvl.rename(columns={'L_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(al_lvl, ['Lvl']), hide_index=True, use_container_width=True)
                with al_c2:
                    st.markdown('<div class="domain-header cv-bg">💰 All-Time Company Value (CV)</div>', unsafe_allow_html=True)
                    al_cv = current_snapshots[['C_Rank', 'Player Name', 'CV']].sort_values('C_Rank')
                    al_cv.rename(columns={'C_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(al_cv, ['CV']), hide_index=True, use_container_width=True)
                with al_c3:
                    st.markdown('<div class="domain-header dc-bg">🎁 All-Time Donations (DC)</div>', unsafe_allow_html=True)
                    al_dc = current_snapshots[['D_Rank', 'Player Name', 'DC']].sort_values('D_Rank')
                    al_dc.rename(columns={'D_Rank': 'Rank'}, inplace=True)
                    st.dataframe(format_table(al_dc, ['DC']), hide_index=True, use_container_width=True)
