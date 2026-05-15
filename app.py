import base64
import calendar
import json
from datetime import date
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION & SECRETS ---
# In a local environment, replace these with actual string values or environment variables
SPREADSHEET_URL = "YOUR_GOOGLE_SHEET_URL_HERE"
ENCODED_CREDS = "YOUR_BASE64_ENCODED_JSON_CREDS_HERE"


# --- 2. DATABASE & DATA PROCESSING ---
def load_mapped_data():
    try:
        decoded_creds = base64.b64decode(ENCODED_CREDS).decode("utf-8")
        creds_dict = json.loads(decoded_creds)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(SPREADSHEET_URL)

        ref_df = pd.DataFrame(sh.worksheet("Reference_Data").get_all_records())
        player_map = (
            ref_df[ref_df["ID_Type"] == "Player"]
            .set_index("ID_Value")["Display_Name"]
            .to_dict()
        )
        status_map = (
            ref_df[ref_df["ID_Type"] == "Player"]
            .set_index("ID_Value")["Status"]
            .to_dict()
        )
        corp_map = (
            ref_df[ref_df["ID_Type"] == "Corp"]
            .set_index("ID_Value")["Display_Name"]
            .to_dict()
        )

        raw_stats_ws = sh.worksheet("Corporation_Stats")
        stats_df = pd.DataFrame(raw_stats_ws.get_all_records())

        stats_df["Date"] = pd.to_datetime(
            stats_df["Date"], format="mixed", errors="coerce"
        )
        stats_df = stats_df.dropna(subset=["Date"])

        stats_df["Player Name"] = (
            stats_df["UID"].map(player_map).fillna(stats_df["UID"])
        )
        stats_df["Corp Name"] = (
            stats_df["Corp_ID"].map(corp_map).fillna(stats_df["Corp_ID"])
        )
        stats_df["Status"] = stats_df["UID"].map(status_map).fillna("Inactive")

        for col in ["Lvl", "CV", "DC"]:
            stats_df[col] = (
                pd.to_numeric(stats_df[col], errors="coerce").fillna(0)
            )

        stats_df = stats_df.sort_values(["UID", "Date"])

        # Gains Calculation
        stats_df["Days_Gap"] = stats_df.groupby("UID")["Date"].diff().dt.days
        for col in ["Lvl", "CV", "DC"]:
            stats_df[f"{col}_Raw_Diff"] = stats_df.groupby("UID")[col].diff()

            def sanitize(row, column):
                diff, gap = row[f"{column}_Raw_Diff"], row["Days_Gap"]
                if pd.isna(diff) or diff < 0 or gap > 10:
                    return 0
                if column == "DC" and diff > 150000:
                    return 0
                if column == "CV" and diff > 100000:
                    return 0
                return diff

            stats_df[f"{col} Gain"] = (
                stats_df.apply(lambda r: sanitize(r, col), axis=1).fillna(0)
            )

        return stats_df, sh, player_map, status_map, corp_map
    except Exception as e:
        print(f"❌ Connection or Processing Failed: {e}")
        return pd.DataFrame(), None, {}, {}, {}


# --- STREAK CALCULATION ENGINE ---
def calculate_streak_details(player_df, metric_col, type_label, latest_corp_date):
    p_sorted = player_df.sort_values("Date", ascending=True)
    streaks = []
    current_streak = []

    for idx, row in p_sorted.iterrows():
        if row[metric_col]:
            current_streak.append(row["Date"])
        else:
            if current_streak:
                streaks.append(
                    {
                        "Type": type_label,
                        "Name": row["Player Name"],
                        "Weeks": len(current_streak),
                        "Start Date": current_streak[0],
                        "End Date": current_streak[-1],
                        "Is Active": current_streak[-1] == latest_corp_date,
                    }
                )
                current_streak = []
    if current_streak:
        streaks.append(
            {
                "Type": type_label,
                "Name": p_sorted.iloc[-1]["Player Name"],
                "Weeks": len(current_streak),
                "Start Date": current_streak[0],
                "End Date": current_streak[-1],
                "Is Active": p_sorted.iloc[-1]["Date"] == latest_corp_date
                and p_sorted.iloc[-1][metric_col],
            }
        )
    return streaks


def stringify_streaks(history_list):
    act, lng, run = 0, 0, 0
    for val in history_list:
        if val:
            run += 1
            lng = max(lng, run)
        else:
            run = 0
    for val in reversed(history_list):
        if val:
            act += 1
        else:
            break
    return f"{act} ({lng})"


# --- 3. MAIN ANALYTICS GENERATOR ---
def run_analytics():
    print("🔄 Initializing Mapped Data Pipelines...")
    df, sh, player_map, status_map, corp_map = load_mapped_data()

    if df.empty:
        print("❌ Data pipeline empty. Execution aborted.")
        return

    # Global Pre-Calculations
    df["L3"] = (
        df.groupby("Date")["Lvl Gain"].rank(ascending=False, method="min") <= 3
    )
    df["C3"] = (
        df.groupby("Date")["CV Gain"].rank(ascending=False, method="min") <= 3
    )
    df["D3"] = (
        df.groupby("Date")["DC Gain"].rank(ascending=False, method="min") <= 3
    )
    df["D1K"] = df["DC Gain"] >= 1000
    df["Month_Key"] = df["Date"].dt.to_period("M")

    # Simulate weekly award winners
    award_winners = []
    for d in df["Date"].unique():
        wk = df[df["Date"] == d].copy()
        if not wk.empty:
            wk["LR"] = wk["Lvl Gain"].rank(ascending=False, method="min")
            wk["CR"] = wk["CV Gain"].rank(ascending=False, method="min")
            wk["DR"] = wk["DC Gain"].rank(ascending=False, method="min")
            wk["RS_Score"] = wk["LR"] + wk["CR"] + wk["DR"]
            rs_winner = wk.sort_values(
                ["RS_Score", "DC Gain"], ascending=[True, False]
            ).iloc[0]["Player Name"]

            l_cut = wk["Lvl"].quantile(0.35)
            rookies = wk[wk["Lvl"] <= l_cut]
            rotw_winner = (
                rookies.sort_values("DC Gain", ascending=False).iloc[0][
                    "Player Name"
                ]
                if not rookies.empty
                else "None"
            )
            award_winners.append(
                {
                    "Date": d,
                    "RS_Winner": rs_winner,
                    "RotW_Winner": rotw_winner,
                }
            )

    df = df.merge(pd.DataFrame(award_winners), on="Date", how="left")
    df["is_RS"] = df["Player Name"] == df["RS_Winner"]
    df["is_RotW"] = df["Player Name"] == df["RotW_Winner"]

    # Select target corporation automatically (mimicking the sidebar default)
    selected_corp_name = sorted(df["Corp Name"].unique())[0]
    print(f"📊 Processing Target Corporation: {selected_corp_name}")

    full_corp_history = df[df["Corp Name"] == selected_corp_name]
    latest_player_snapshots = (
        full_corp_history.sort_values("Date")
        .groupby("Player Name")
        .last()
        .reset_index()
    )
    active_player_names = latest_player_snapshots[
        latest_player_snapshots["Status"]
        .astype(str)
        .str.contains("Active", case=False, na=False)
    ]["Player Name"].tolist()

    active_df = full_corp_history[
        full_corp_history["Player Name"].isin(active_player_names)
    ].copy()
    latest_date = active_df["Date"].max()

    # --- OUTPUT BLOCK A: OVERVIEW SUMMARY ---
    latest_df = active_df[active_df["Date"] == latest_date]
    print(f"\n--- Overview Summary ({latest_date.strftime('%Y-%m-%d')}) ---")
    print(f"Active Roster Count: {len(latest_df)}")
    print(f"Average Fleet Level: {latest_df['Lvl'].mean():,.1f}")
    print(f"Total Portfolio Value: ${latest_df['CV'].sum():,.0f}M")
    print(f"Total Historic Donations: {latest_df['DC'].sum():,.0f}")

    # --- OUTPUT BLOCK B: WEEKLY LEADERBOARD SCOPES ---
    print("\n--- Weekly Leaderboards (Top Gains) ---")
    week_data = active_df[active_df["Date"] == latest_date].copy()
    for metric, display_label in [
        ("Lvl Gain", "Δ Level"),
        ("CV Gain", "Δ Company Value"),
        ("DC Gain", "Δ Donations"),
    ]:
        sorted_board = week_data[["Player Name", metric]].sort_values(
            metric, ascending=False
        )
        print(f"\n🔹 {display_label} Rankings:")
        print(sorted_board.to_string(index=False))

    # --- OUTPUT BLOCK C: ALL-TIME STANDINGS ---
    print("\n--- All-Time Standings (Active Members Only) ---")
    current_snapshots = latest_player_snapshots[
        latest_player_snapshots["Status"]
        .astype(str)
        .str.contains("Active", case=False, na=False)
    ].copy()
    if not current_snapshots.empty:
        current_snapshots["L_Rank"] = current_snapshots["Lvl"].rank(
            ascending=False, method="min"
        )
        current_snapshots["C_Rank"] = current_snapshots["CV"].rank(
            ascending=False, method="min"
        )
        current_snapshots["D_Rank"] = current_snapshots["DC"].rank(
            ascending=False, method="min"
        )
        current_snapshots["Rank_Sum"] = (
            current_snapshots["L_Rank"]
            + current_snapshots["C_Rank"]
            + current_snapshots["D_Rank"]
        )
        current_snapshots["Overall_Rank"] = current_snapshots["Rank_Sum"].rank(
            ascending=True, method="min"
        )

        master_board = current_snapshots[
            ["Overall_Rank", "Player Name", "Lvl", "CV", "DC"]
        ].sort_values("Overall_Rank")
        print(master_board.to_string(index=False))

    # --- OUTPUT BLOCK D: ELITE STREAKS ENGINE ---
    print("\n--- Processing Longest Streaks Data Model ---")
    metric_map = {
        "L3": "Δ Lvl",
        "C3": "Δ CV",
        "D3": "Δ DC",
        "D1K": "1k+ DC",
        "is_RotW": "RotW",
        "is_RS": "RS",
    }
    final_s = []
    all_historical_streaks = []

    for uid in active_df["UID"].unique():
        p_h = active_df[active_df["UID"] == uid]
        p_name = p_h["Player Name"].iloc[0]

        history_metrics = {}
        for col_key, label in metric_map.items():
            history_metrics[col_key] = (
                p_h.sort_values("Date", ascending=True)[col_key].tolist()
            )
            extracted = calculate_streak_details(
                p_h, col_key, label, latest_date
            )
            all_historical_streaks.extend(extracted)

        final_s.append(
            {
                "Player Name": p_name,
                "Lvl Top 3": stringify_streaks(history_metrics["L3"]),
                "CV Top 3": stringify_streaks(history_metrics["C3"]),
                "DC Top 3": stringify_streaks(history_metrics["D3"]),
                "1,000+ DC": stringify_streaks(history_metrics["D1K"]),
            }
        )

    streaks_summary_df = pd.DataFrame(final_s)
    print(streaks_summary_df.to_string(index=False))

    print("\n🚀 Analytics computation complete. Data successfully modeled.")


if __name__ == "__main__":
    run_analytics()
