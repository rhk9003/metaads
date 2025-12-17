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
        st.sidebar.write("Debug: Initializing GoogleServices...")
        
        # Priority 1: Check Streamlit Secrets (Nested Section)
        if "gcp_service_account" in st.secrets:
            st.sidebar.write("Debug: Found [gcp_service_account]")
            service_account_info = dict(st.secrets["gcp_service_account"])
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        
        # Priority 1.5: Check Streamlit Secrets (Raw JSON String)
        # This is easier for users: just paste the whole JSON into a string variable
        elif "gcp_json" in st.secrets:
            st.sidebar.write("Debug: Found gcp_json")
            try:
                service_account_info = json.loads(st.secrets["gcp_json"])
                self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
                st.sidebar.success("Debug: loaded creds from gcp_json")
            except json.JSONDecodeError as e:
                st.sidebar.error(f"Debug: JSON Error {e}")
                raise ValueError(f"Invalid JSON in secrets 'gcp_json': {e}")
            except Exception as e:
                st.sidebar.error(f"Debug: Creds Error {e}")
                raise e
        # Priority 1.8: Check Streamlit Secrets (Root Level Fallback)
        elif "private_key" in st.secrets:
            st.sidebar.write("Debug: Found private_key (Root)")
            service_account_info = dict(st.secrets)
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        
        # Priority 2: Check Local File
        elif os.path.exists(service_account_file):
            st.sidebar.write("Debug: Found local file")
            self.creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        
        else:
            st.sidebar.write("Debug: Entering Fallback (Priority 3)")
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
        query = f"name = '{name}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        # Added supportsAllDrives=True to find files in Shared Drives
        results = self.drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        return None
    def find_folder_in_drive(self, name):
        """Finds a folder by name in Drive, returns ID if found."""
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        # Added supportsAllDrives=True to find folders in Shared Drives
        results = self.drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        return None
    # Function to find the Root Folder (Shared from User)
    def get_root_folder_id(self):
        # We look for a specific folder that the user MUST satisfy
        # This bypasses the 0-byte limit of the service account itself
        FOLDER_NAME = "Meta_Ads_System" # User must create this
        folder_id = self.find_folder_in_drive(FOLDER_NAME)
        return folder_id
    def create_folder(self, name, parent_id=None):
        """Creates a new folder, optionally inside a parent."""
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        # Added supportsAllDrives=True
        file = self.drive_service.files().create(
            body=file_metadata, 
            fields='id',
            supportsAllDrives=True
        ).execute()
        return file.get('id')
    def create_doc(self, title, folder_id=None):
        """Creates a new Google Doc, optionally inside a folder."""
        doc_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        if folder_id:
            doc_metadata['parents'] = [folder_id]
            
        # Added supportsAllDrives=True
        doc = self.drive_service.files().create(
            body=doc_metadata, 
            fields='id',
            supportsAllDrives=True
        ).execute()
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
        Strategy:
        1. Find 'Meta_Ads_System' folder (Shared from User).
        2. If not found -> RAISE ERROR (User must create it).
        3. Find/Create 'CustomerName' folder INSIDE 'Meta_Ads_System'.
        4. Create Doc INSIDE 'CustomerName' folder.
        """
        doc_name = f"{case_id}_meta廣告上刊文件"
        st.sidebar.info(f"Debug: Checking doc '{doc_name}'")
        
        existing_doc_id = self.find_file_in_drive(doc_name)
        if existing_doc_id:
            st.sidebar.success(f"Debug: Doc found ({existing_doc_id})")
            print(f"Document '{doc_name}' already exists. ID: {existing_doc_id}")
            try:
                self.share_file(existing_doc_id, customer_email)
                self.share_file(existing_doc_id, ADMIN_EMAIL)
            except:
                pass 
            return existing_doc_id
        else:
            print(f"Creating new document: {doc_name}")
            st.sidebar.info("Debug: Doc not found, creating...")
            
            # 0. Find Root Folder (CRITICAL FIX for 0 Quota)
            st.sidebar.text("Debug: Searching for 'Meta_Ads_System'...")
            root_id = self.get_root_folder_id()
            
            if not root_id:
                st.sidebar.error("❌ Critical: 'Meta_Ads_System' folder NOT FOUND.")
                st.sidebar.warning("請確保您已在 Google Drive 建立 'Meta_Ads_System' 資料夾並分享給機器人帳號！")
                raise FileNotFoundError("找不到根目錄 'Meta_Ads_System'。請在您的 Google Drive 建立此資料夾並分享給 Service Account。")
            else:
                st.sidebar.success(f"✅ Found Root Folder: {root_id}")
            # 1. Determine Customer Folder Name
            if "_" in str(case_id):
                folder_name = str(case_id).split("_")[0]
            else:
                folder_name = str(case_id)
            
            # 2. Check/Create Customer Folder INSIDE Root
            st.sidebar.text(f"Debug: Searching/Creating Subfolder '{folder_name}'...")
            folder_id = self.find_folder_in_drive(folder_name)
            
            if not folder_id:
                st.sidebar.text(f"Debug: Creating '{folder_name}' inside Root...")
                try:
                    folder_id = self.create_folder(folder_name, parent_id=root_id)
                    st.sidebar.success(f"✅ Created Subfolder: {folder_id}")
                except Exception as e:
                     st.sidebar.error(f"❌ Failed to create subfolder: {e}")
                     raise e
            else:
                st.sidebar.info(f"Debug: Found existing subfolder {folder_id}")
            
            # 3. Create Doc inside Customer Folder
            st.sidebar.text("Debug: Creating Document...")
            try:
                new_doc_id = self.create_doc(doc_name, folder_id=folder_id)
                st.sidebar.success(f"✅ Created Document: {new_doc_id}")
            except Exception as e:
                st.sidebar.error(f"❌ Failed to create document: {e}")
                raise e
            
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
        
        # --- Attempt to insert image ---
        image_url = ad_data.get('image_url')
        if image_url:
            try:
                # We need to refresh the index because we just inserted text
                doc = self.docs_service.documents().get(documentId=doc_id).execute()
                content = doc.get('body').get('content')
                last_index = content[-1]['endIndex'] - 1 
                
                image_requests = [
                    {
                        'insertInlineImage': {
                            'uri': image_url,
                            'location': {
                                'index': last_index
                            },
                            'objectSize': {
                                'width': {
                                    'magnitude': 400,
                                    'unit': 'PT'
                                }
                            }
                        }
                    },
                     {
                        'insertText': {
                             'location': {
                                'index': last_index + 1 # Insert newline after image (conceptually)
                            },
                            'text': "\n"
                        }
                    }
                ]
                self.docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': image_requests}).execute()
                print(f"Image inserted successfully: {image_url}")
            except Exception as e:
                print(f"Failed to insert image (URL might be invalid or private): {e}")
        return block_name
