import os
import datetime
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import streamlit as st
# Constants
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]
# You might want to move these to environment variables or a config file
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1zXHavJqhOBq1-m_VR7sxMkeOHdXoD9EmQCEM1Nl816I/edit?usp=sharing"
ADMIN_EMAIL = "rhk9903@gmail.com"
# Column Indices (0-based) - Adjust these if the sheet structure changes
# Assuming simple structure for now, but in a real app, searching by header name is better.
# Let's try to find headers dynamically in the code.
class GoogleServices:
    def __init__(self, service_account_file='gen-lang-client-0057298651-12025f130563.json'):
        self.creds = None
        
        # Priority 1: Check Streamlit Secrets (Nested Section)
        # We look for a section named "gcp_service_account" or similar in secrets.toml
        if "gcp_service_account" in st.secrets:
            # st.secrets returns a primitive dict-like object, Credentials checks for type dict
            service_account_info = dict(st.secrets["gcp_service_account"])
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        # Priority 1.5: Check Streamlit Secrets (Root Level)
        # In case user pasted the keys directly without [gcp_service_account] header
        elif "private_key" in st.secrets:
            service_account_info = dict(st.secrets)
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        
        # Priority 2: Check Local File
        elif os.path.exists(service_account_file):
            self.creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        
        else:
            # Priority 3: Check for ANY json file that looks like a key in the current dir (Fallback)
            json_files = [f for f in os.listdir('.') if f.endswith('.json')]
            for f in json_files:
                try:
                    # quick check if it's a service account file
                    with open(f) as json_file:
                        data = json.load(json_file)
                        if data.get('type') == 'service_account':
                            self.creds = Credentials.from_service_account_file(f, scopes=SCOPES)
                            break
                except:
                    continue
            
            if not self.creds:
                raise FileNotFoundError(f"Could not find valid credentials in st.secrets or local file '{service_account_file}'.")
        self.gc = gspread.authorize(self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self.docs_service = build('docs', 'v1', credentials=self.creds)
    def get_case_id_by_email(self, email):
        """
        Scans the master sheet for the email and returns the associated Case ID.
        """
        try:
            # Open the sheet by URL
            sh = self.gc.open_by_url(MASTER_SHEET_URL)
            worksheet = sh.get_worksheet(0) # Assuming data is in the first sheet
            # Get all records to find headers
            # records = worksheet.get_all_records() # usage dependent on headers
            
            # Alternative: get all values and find indices
            all_values = worksheet.get_all_values()
            if not all_values:
                return None
            
            headers = [h.lower().strip() for h in all_values[0]]
            
            try:
                # Flexible matching for headers
                email_col_idx = -1
                case_id_col_idx = -1
                
                for idx, h in enumerate(headers):
                    if "email" in h or "信箱" in h:
                        email_col_idx = idx
                    if "case" in h or "id" in h or "編號" in h or "案件" in h:
                        case_id_col_idx = idx
                
                if email_col_idx == -1 or case_id_col_idx == -1:
                    # Fallback to column A and B if headers not found, or raise error
                    # Let's assume A=Timestamp (common), B=Email, C=CaseID as a guess if failed? 
                    # Or just configurable constants.
                    # For now, let's look for specific columns if we can't find them dynamically.
                    print("Could not likely identify columns by header. Checking raw data.")
                    pass
            except Exception as e:
                print(f"Header parsing error: {e}")
            # Simplest approach: Use gspread's find method if the email is unique
            # precise matching
            cell = worksheet.find(email)
            if cell:
                # success finding user. Now we need to know which column is the Case ID.
                # Assuming Case ID is in a specific column relative to Email or fixed.
                # Let's re-scan headers more robustly or just return the row data.
                
                # Fetching the whole row
                row_values = worksheet.row_values(cell.row)
                
                # We need to explicitly know which column is Case ID. 
                # Let's assume it's the column named "Case ID" or similar.
                # If we rely on get_all_records(), it creates a dict with keys as headers.
                records = worksheet.get_all_records()
                for record in records:
                    # Normalize keys to lower case for search
                    normalized_record = {k.lower(): v for k, v in record.items()}
                    # Check if this record matches the email
                    # Keys might be 'Email Address', 'User Email', etc.
                    found_email = False
                    for k, v in normalized_record.items():
                        if ('email' in k or '信箱' in k) and str(v).strip().lower() == email.strip().lower():
                            found_email = True
                            break
                    
                    if found_email:
                        # Find Case ID
                        for k, v in normalized_record.items():
                            if '案件編號' in k or 'case' in k:
                                return str(v)
            
            return None
        except Exception as e:
            print(f"Error reading sheet: {e}")
            return None
    def find_file_in_drive(self, name):
        """Finds a file by name in Drive, returns ID if found."""
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
        results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        return None
    def find_folder_in_drive(self, name):
        """Finds a folder by name in Drive, returns ID if found."""
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        return None
    def create_folder(self, name):
        """Creates a new folder."""
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')
    def create_doc(self, title, folder_id=None):
        """Creates a new Google Doc, optionally inside a folder."""
        doc_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        if folder_id:
            doc_metadata['parents'] = [folder_id]
            
        doc = self.drive_service.files().create(body=doc_metadata, fields='id').execute()
        return doc.get('id')
    def share_file(self, file_id, email, role='writer'):
        """Shares a file with a specific email."""
        def callback(request_id, response, exception):
            if exception:
                print(f"Error sharing with {email}: {exception}")
        batch = self.drive_service.new_batch_http_request(callback=callback)
        user_permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email
        }
        batch.add(self.drive_service.permissions().create(
                fileId=file_id,
                body=user_permission,
                fields='id',
        ))
        batch.execute()
    def ensure_doc_exists_and_share(self, case_id, customer_email):
        """
        Checks if 'CASEID_meta廣告上刊文件' exists.
        If yes, returns ID.
        If no, creates it in the customer folder, shares with customer and admin.
        """
        doc_name = f"{case_id}_meta廣告上刊文件"
        existing_doc_id = self.find_file_in_drive(doc_name)
        if existing_doc_id:
            print(f"Document '{doc_name}' already exists. ID: {existing_doc_id}")
            # Ensure permissions are set (idempotent-ish, or just skip)
            # We can re-share just in case
            try:
                self.share_file(existing_doc_id, customer_email)
                self.share_file(existing_doc_id, ADMIN_EMAIL)
            except:
                pass 
            return existing_doc_id
        else:
            print(f"Creating new document: {doc_name}")
            
            # 1. Determine Customer Folder Name
            # Split case_id by '_' to get the prefix. e.g. "Nike_Seasonal" -> "Nike"
            if "_" in str(case_id):
                folder_name = str(case_id).split("_")[0]
            else:
                folder_name = str(case_id)
            
            # 2. Check/Create Folder
            folder_id = self.find_folder_in_drive(folder_name)
            if not folder_id:
                print(f"Creating new folder: {folder_name}")
                folder_id = self.create_folder(folder_name)
                # Optional: Share folder? The user didn't explicitly ask to share the folder, 
                # but usually it's good practice. However, adhering strictly to "new doc stored in folder".
                # If we share the folder, they inherit access to everything inside.
                # Let's share the folder too for convenience? Or stick to file sharing.
                # User request: "stored in client name folder". 
                # I will create the doc INSIDE this folder.
            
            # 3. Create Doc inside Folder
            new_doc_id = self.create_doc(doc_name, folder_id=folder_id)
            
            self.share_file(new_doc_id, customer_email)
            self.share_file(new_doc_id, ADMIN_EMAIL)
            return new_doc_id
    def append_ad_data_to_doc(self, doc_id, ad_data):
        """
        Appends the formatted ad data to the Google Doc.
        ad_data is a dict containing header info.
        """
        # Define the block name provided in the request
        block_name = f"{ad_data.get('ad_name_id')}_{ad_data.get('image_name_id')}"
        
        # Current time for the file update logic if needed, but we write to doc body
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Construct the text content
        text_content = (
            f"\n\n--------------------------------------------------\n"
            f"廣告組合 ID: {block_name}\n"
            f"填寫時間: {ad_data.get('fill_time')}\n"
            f"廣告名稱/編號: {ad_data.get('ad_name_id')}\n"
            f"對應圖片名稱/編號: {ad_data.get('image_name_id')}\n"
            f"對應圖片雲端網址: {ad_data.get('image_url')}\n"
            f"廣告標題: {ad_data.get('headline')}\n"
            f"廣告主文案:\n{ad_data.get('main_copy')}\n"
            f"廣告到達網址: {ad_data.get('landing_url')}\n"
            f"--------------------------------------------------\n"
        )
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1, # Insert at the beginning or end? Usually appending is safer with endOfSegmentLocation but insertText requires index.
                                    # To append, we need to know the document length, which requires a read. 
                                    # However, inserting at index 1 (start) puts it at the top (stack style), 
                                    # or we can try to find the end.
                    },
                    'text': text_content
                }
            }
        ]
        
        # To append efficiently without reading size, usually we use EndOfSegmentLocation if available in specific update methods, 
        # but pure insertText takes an index. 
        # Let's read the doc length first to append to the end.
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        content = doc.get('body').get('content')
        last_index = content[-1]['endIndex'] - 1 
        requests = [
             {
                'insertText': {
                    'location': {
                        'index': last_index
                    },
                    'text': text_content
                }
            }
        ]
        self.docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        return block_name
