import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

# Custom UI Styling
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border: 1px solid #d1d5db;
        padding: 15px;
        border-radius: 10px;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e293b;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏆 RCTT Corporation Hub Network</div>', unsafe_allow_html=True)

# --- 2. DATABASE CONNECTION ---
@st.cache_data(ttl=60) # Cache data for 1 minute
def load_data():
    try:
        # Pull secrets from Streamlit
        s = st.secrets["connections"]["gsheets"]
        
        # CHANGE MADE HERE: 
        # We no longer use .replace("\\n", "\n") because the triple quotes 
        # in your Secrets dashboard handle the newlines naturally.
        creds_info = {
            "type": s["type"],
            "project_id": s["project_id"],
            "private_key_id": s["private_key_id"],
            "private_key": s["private_key"], 
            "client_email": s["client_email"],
            "client_id": s["client_id"],
            "auth_uri": s["auth_uri"],
            "token_uri": s["token_uri"],
            "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
            "client_x509_cert_url": s["client_x509_cert_url"]
        }
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(creds)
        
        # Connect to your specific Spreadsheet and Worksheet
        sh = gc.open_by_url(s["spreadsheet"])
        worksheet = sh.worksheet("Corporation_Stats")
        
        # Fetch data and convert to DataFrame
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    
    except Exception as e:
        st.error(f"❌ Connection Failed: {e}")
        return pd.DataFrame(), None

# --- 3. DATA PROCESSING ---
df, worksheet = load_data()

if not df.empty:
    # Ensure numeric columns are actually numbers
    df['Date'] = pd.to_datetime(df['Date'])
    df['Company Value'] = pd.to_numeric(df['Company Value'], errors='coerce').fillna(0)
    df['Donation Count'] = pd.to_numeric(df['Donation Count'], errors='coerce').fillna(0)
    df['Player Level'] = pd.to_numeric(df['Player Level'], errors='coerce').fillna(1)

    # --- 4. DASHBOARD FILTERS ---
    st.sidebar.header("Navigation")
    corps = sorted(df['Corp Name'].unique())
    selected_corp = st.sidebar.selectbox("Choose Corporation", corps)
    
    # Filter for selected corp and most recent update date
    corp_data = df[df['Corp Name'] == selected_corp]
    latest_date = corp_data['Date'].max()
    latest_stats = corp_data[corp_data['Date'] == latest_date]

    # --- 5. TOP LEVEL METRICS ---
    st.subheader(f"📈 {selected_corp} Overview (As of {latest_date.date()})")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Members", len(latest_stats))
    m2.metric("Total Net Worth", f"${latest_stats['Company Value'].sum():,.0f}M")
    m3.metric("Total Donations", f"{latest_stats['Donation Count'].sum():,.0f}")
    avg_lvl = latest_stats['Player Level'].mean()
    m4.metric("Average Level", f"{avg_lvl:.1f}")

    # --- 6. LEADERBOARDS ---
    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.write("### 💰 Top Company Value")
        top_val = latest_stats[['Player Name', 'Company Value']].sort_values(by='Company Value', ascending=False).head(10)
        st.dataframe(top_val, use_container_width=True, hide_index=True)

    with col_right:
        st.write("### 🟢 Top Donators")
        top_don = latest_stats[['Player Name', 'Donation Count']].sort_values(by='Donation Count', ascending=False).head(10)
        st.dataframe(top_don, use_container_width=True, hide_index=True)

    # --- 7. ADMIN ENTRY FORM ---
    st.divider()
    with st.expander("🛠️ Admin: Add/Update Member Stats"):
        with st.form("admin_form", clear_on_submit=True):
            st.write("Submit stats for a player. This will add a new row to the database.")
            c1, c2, c3 = st.columns(3)
            f_date = c1.date_input("Report Date", date.today())
            f_corp = c1.selectbox("Corporation", corps)
            f_name = c2.text_input("Player Name")
            f_lvl = c2.number_input("Player Level", 1, 150, 50)
            f_val = c3.number_input("Company Value (Millions)", 0, 1000000, 100)
            f_don = c3.number_input("Donation Count", 0, 50000, 0)
            
            if st.form_submit_button("Submit Stats to Google Sheets"):
                if f_name:
                    try:
                        new_row = [str(f_date), f_corp, f_name, f_lvl, f_val, f_don]
                        worksheet.append_row(new_row)
                        st.success(f"Successfully logged stats for {f_name}!")
                        st.cache_data.clear() # Forces app to reload fresh data
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error submitting data: {e}")
                else:
                    st.warning("Please enter a player name before submitting.")

else:
    st.warning("⚠️ Waiting for data... Please check your 'Secrets' configuration and ensure the Service Account email has 'Editor' access to the Spreadsheet.")
