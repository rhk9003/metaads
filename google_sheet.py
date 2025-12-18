import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import json
from datetime import datetime

class GoogleSheetService:
    def __init__(self):
        self.scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds = None
        self.client = None
        self.sheet = None
        self.columns = [
            "Email", "case_id", "party_a", "provider", "plan", "start_date", "pay_day", "pay_date",
            "chk_ad_account", "chk_pixel", "chk_fanpage", "chk_bm", "fanpage_url", "landing_url",
            "comp1", "comp2", "comp3", "who_problem", "what_problem", "how_solve", "budget",
            "last_update_at", "msg_type", "plan_raw", "display_label"
        ]
        self._connect()

    def _connect(self):
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
                self.creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, self.scope)
            else:
                self.creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", self.scope)
            
            self.client = gspread.authorize(self.creds)
            
            sheet_url = st.secrets["sheets"]["url"] if "sheets" in st.secrets and "url" in st.secrets["sheets"] else "https://docs.google.com/spreadsheets/d/1zXHavJqhOBq1-m_VR7sxMkeOHdXoD9EmQCEM1Nl816I/edit?usp=sharing"
            self.sheet = self.client.open_by_url(sheet_url).sheet1
        except Exception as e:
            st.error(f"Google Sheet Connection Error: {e}")

    def get_user_by_email(self, email):
        if not self.sheet:
            return None
        try:
            records = self.sheet.get_all_records()
            for row in records:
                if str(row.get("Email", "")).strip().lower() == str(email).strip().lower():
                    return row
            return None
        except Exception as e:
            st.error(f"Error reading sheet: {e}")
            return None

    def create_or_update_user(self, client_data):
        if not self.sheet:
            return False
        
        try:
            email = client_data.get("Email")
            if not email:
                return False

            client_data['last_update_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                cell = self.sheet.find(email)
            except:
                cell = None

            headers = self.sheet.row_values(1)
            
            # Prepare row data maintaining column order
            row_values = []
            
            if cell:
                # Update existing row
                row_idx = cell.row
                # We update each cell that exists in client_data
                # But to save API calls, constructing the whole row is tricky if we don't know the exact order 
                # or if we don't want to overwrite other columns.
                # safely update only provided fields
                
                for key, value in client_data.items():
                    if key in headers:
                        col_idx = headers.index(key) + 1
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False)
                        self.sheet.update_cell(row_idx, col_idx, value)
            else:
                # New Row
                # Ensure all headers exist or map strictly to self.columns
                new_row = []
                # If sheet headers are empty, we might should init them?
                # Assuming sheet is prepared as per user request.
                
                if not headers:
                    # Init headers if empty (optional safety)
                    self.sheet.append_row(self.columns)
                    headers = self.columns

                for h in headers:
                    val = client_data.get(h, "")
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    new_row.append(val)
                self.sheet.append_row(new_row)
                
            return True
        except Exception as e:
            st.error(f"Error saving to sheet: {e}")
            return False

def get_sheet_service():
    return GoogleSheetService()
