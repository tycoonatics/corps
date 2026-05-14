import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from datetime import date

st.set_page_config(page_title="RCTT Hub", layout="wide")

@st.cache_data(ttl=60)
def load_data():
    try:
        # 1. Get the encoded string from secrets
        encoded_creds = st.secrets["connections"]["gsheets"]["encoded_creds"]
        
        # 2. Decode the Base64 back into JSON
        decoded_creds = base64.b64decode(encoded_creds).decode("utf-8")
        creds_dict = json.loads(decoded_creds)
        
        # 3. Authenticate
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        # 4. Open the sheet
        sh = gc.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"])
        worksheet = sh.worksheet("Corporation_Stats")
        
        df = pd.DataFrame(worksheet.get_all_records())
        return df, worksheet
    except Exception as e:
        st.error(f"Failed to connect: {e}")
        return pd.DataFrame(), None

st.title("🏆 RCTT Corporation Hub Network")
df, worksheet = load_data()

if not df.empty:
    st.success("Connection Stable!")
    # ... Rest of your dashboard code ...
    st.dataframe(df)
    
    with st.form("add_data"):
        st.write("### Quick Add")
        n = st.text_input("Name")
        if st.form_submit_button("Submit"):
            worksheet.append_row([str(date.today()), "RCTT", n, 0, 0, 0])
            st.rerun()
else:
    st.info("Waiting for Base64 credentials...")
