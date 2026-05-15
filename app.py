# --- UPDATED DATA PROCESSING SECTION ---
@st.cache_data(ttl=5)
def load_mapped_data():
    try:
        # ... [Your existing connection code here] ...

        stats_df = stats_df.sort_values(['UID', 'Date'])

        # 1. Track the gap between entries to find when they left
        stats_df['Days_Gap'] = stats_df.groupby('UID')['Date'].diff().dt.days
        
        for col in ['Lvl', 'CV', 'DC']:
            # Calculate the raw jump
            stats_df[f'{col}_Raw_Diff'] = stats_df.groupby('UID')[col].diff()
            
            # --- THE "STRICT FILTER" FIX ---
            # We define a "Spike Threshold". 
            # If the jump is negative, OR the gap is too long, OR the gain is impossibly high (e.g. > 100k DC),
            # we set that week's gain to 0.
            def sanitize_gains(row, column):
                diff = row[f'{column}_Raw_Diff']
                gap = row['Days_Gap']
                
                # Check for re-entry spikes or impossible jumps
                if pd.isna(diff) or diff < 0 or gap > 10:
                    return 0
                
                # Specifically for DC: if a single week gain is over 150k, it's likely a data reset error
                if column == 'DC' and diff > 150000:
                    return 0
                    
                return diff

            stats_df[f'{col} Gain'] = stats_df.apply(lambda r: sanitize_gains(r, col), axis=1)
            
        return stats_df, raw_stats_ws, player_map, status_map, corp_map
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}

# --- UPDATED PROFILE METRICS SECTION ---
# Inside your Tab 5 (Profiles) logic:

with tab_profiles:
    # ... [Search Member selectbox logic] ...

    # Filter out the 0s when calculating the AVERAGE, so weeks they weren't there don't pull the average down
    # and spikes don't pull it up.
    actual_activity = p_history[p_history['DC Gain'] > 0]
    avg_dc = actual_activity['DC Gain'].mean() if not actual_activity.empty else 0

    m_col3.metric("Avg Weekly DC", f"+{int(avg_dc):,}")
    m_col4.metric("Total DC Contribution", f"{int(p_history['DC Gain'].sum()):,}")
