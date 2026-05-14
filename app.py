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
        
        # Decode the Base64 key to get the original PEM string
        # This bypasses all Streamlit secret formatting issues
        encoded_key = s["private_key"]
        decoded_key = base64.b64decode(encoded_key).decode("utf-8")
        
        # Rebuild the newline characters properly
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
        
        workbook = client.open_by_url(s["spreadsheet"])
        worksheet = workbook.worksheet("Corporation_Stats")
        records = worksheet.get_all_records()
        
        return pd.DataFrame(records), worksheet
    except Exception as e:
        st.error(f"Authentication Failed: {e}")
        return pd.DataFrame(), None

df, target_worksheet = load_data_from_sheets()

if not df.empty:
    st.success("Successfully connected to the database!")
    # Render your leaderboards here using the df
    st.dataframe(df)
else:
    st.warning("Database empty or connection pending.")
