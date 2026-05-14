import streamlit as st
import pandas as pd
from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import base64

st.set_page_config(page_title="RCTT Corporation Hub", page_icon="🏆", layout="wide")

st.title("🏆 RCTT Corporation Hub Network")

@st.cache_data(ttl=5)
def load_data_from_sheets():
    try:
        s = st.secrets["connections"]["gsheets"]
        b64_key = s["private_key"].strip()
        
        # PADDING FIXER: Add missing '=' if the string length isn't a multiple of 4
        missing_padding = len(b64_key) % 4
        if missing_padding:
            b64_key += '=' * (4 - missing_padding)
            
        # Decode and clean
        decoded_key = base64.b64decode(b64_key).decode("utf-8")
        final_key = decoded_key.replace("\\n", "\n")
        
        creds_dict = {
            "type": s["type"],
            "project_id": s["project_id"],
            "private_key_id": s["private_key_id"],
            "private_key": final_key,
            "client_email": s["client_email"],
            "client_id": s["client_id"],
            "auth_uri": s["auth_uri"],
            "token_uri": s["token_uri"],
            "auth_provider_x509_cert_url": s["auth_provider_x509_cert_url"],
            "client_x509_cert_url": s["client_x509_cert_url"]
        }
        
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Pull data from your specific sheet
        workbook = client.open_by_url(s["spreadsheet"])
        worksheet = workbook.worksheet("Corporation_Stats")
        records = worksheet.get_all_records()
        
        return pd.DataFrame(records), worksheet
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        return pd.DataFrame(), None

df, target_worksheet = load_data_from_sheets()

if not df.empty:
    st.success("Successfully connected!")
    # Show the data from your RCTT_Hub_DB
    st.dataframe(df, use_container_width=True)
    
    # Simple Admin Form
    with st.form("quick_log"):
        st.write("### Quick Admin Log")
        c1, c2, c3 = st.columns(3)
        p_name = c1.text_input("Player Name")
        p_val = c2.number_input("Company Value", value=1000000)
        p_don = c3.number_input("Donations", value=0)
        
        if st.form_submit_button("Submit"):
            if p_name:
                new_row = [str(date.today()), "RCTT", p_name, 50, p_val, p_don]
                target_worksheet.append_row(new_row)
                st.cache_data.clear()
                st.rerun()
else:
    st.info("Check that the Service Account email is an 'Editor' on your Google Sheet.")
