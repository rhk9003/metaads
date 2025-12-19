import os
import re
import datetime
import json
import gspread
import base64
import requests
import io
import time
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
import streamlit as st

# Constants
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/gmail.send' 
]

MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/1zXHavJqhOBq1-m_VR7sxMkeOHdXoD9EmQCEM1Nl816I/edit?usp=sharing"
ADMIN_EMAIL = "rhk9903@gmail.com"

class GoogleServices:
    def __init__(self, service_account_file='gen-lang-client-0057298651-12025f130563.json'):
        self.creds = None
        st.sidebar.write("Debug: Initializing GoogleServices...")
        self.auth_mode = "service_account"
        self.email_map = None
        
        # 1. Try OAuth
        if "oauth" in st.secrets:
            try:
                oauth_info = st.secrets["oauth"]
                self.creds = UserCredentials(
                    None,
                    refresh_token=oauth_info["refresh_token"],
                    token_uri=oauth_info["token_uri"],
                    client_id=oauth_info["client_id"],
                    client_secret=oauth_info["client_secret"],
                    scopes=SCOPES
                )
                self.auth_mode = "oauth"
                st.sidebar.success("Debug: Auth with OAuth Success!")
            except Exception as e:
                st.sidebar.error(f"Debug: OAuth Error {e}")
                raise e
        
        # 2. Try Service Account (various formats)
        elif "gcp_service_account" in st.secrets:
            service_account_info = dict(st.secrets["gcp_service_account"])
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        elif "gcp_json" in st.secrets:
            service_account_info = json.loads(st.secrets["gcp_json"])
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        elif "private_key" in st.secrets:
            service_account_info = dict(st.secrets)
            self.creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        elif os.path.exists(service_account_file):
            self.creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        
        if not self.creds:
            raise FileNotFoundError("Could not find valid credentials.")

        self.gc = gspread.authorize(self.creds)
        try:
             self.sheet = self.gc.open_by_url(MASTER_SHEET_URL).sheet1
        except Exception as e:
             self.sheet = None

        self.drive_service = build('drive', 'v3', credentials=self.creds)
        self.docs_service = build('docs', 'v1', credentials=self.creds)

    def get_case_id_by_email(self, email):
        try:
            sh = self.gc.open_by_url(MASTER_SHEET_URL)
            worksheet = sh.get_worksheet(0)
            records = worksheet.get_all_records()
            self.email_map = {}
            for row in records:
                row_email = str(row.get('Email') or row.get('email') or row.get('Email Address') or '').strip()
                row_case = str(row.get('Case ID') or row.get('case_id') or row.get('Case_ID') or row.get('案件編號') or '').strip()
                if row_email and row_case:
                    self.email_map[row_email] = row_case
            return self.email_map.get(email.strip())
        except Exception as e:
            st.error(f"Error reading Sheet: {e}")
            return None

    def find_file_in_drive(self, name, parent_id=None):
        query = f"name = '{name}' and mimeType != 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id: query += f" and '{parent_id}' in parents"
        results = self.drive_service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def find_folder_in_drive(self, name, parent_id=None):
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id: query += f" and '{parent_id}' in parents"
        results = self.drive_service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def get_root_folder_id(self):
        return self.find_folder_in_drive("Meta_Ads_System")

    def create_folder(self, name, parent_id=None):
        file_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id: file_metadata['parents'] = [parent_id]
        file = self.drive_service.files().create(body=file_metadata, fields='id', supportsAllDrives=True).execute()
        return file.get('id')

    def create_doc(self, title, folder_id=None):
        doc_metadata = {'name': title, 'mimeType': 'application/vnd.google-apps.document'}
        if folder_id: doc_metadata['parents'] = [folder_id]
        doc = self.drive_service.files().create(body=doc_metadata, fields='id', supportsAllDrives=True).execute()
        return doc.get('id')

    def share_file(self, file_id, email, role='writer'):
        user_permission = {'type': 'user', 'role': role, 'emailAddress': email}
        self.drive_service.permissions().create(fileId=file_id, body=user_permission, fields='id').execute()

    def ensure_doc_exists_and_share(self, case_id, customer_email):
        doc_name = f"{case_id}_meta廣告上刊文件"
        existing_doc_id = self.find_file_in_drive(doc_name)
        if existing_doc_id:
            return existing_doc_id
        
        root_id = self.get_root_folder_id()
        if not root_id:
            raise FileNotFoundError("找不到根目錄 'Meta_Ads_System'。")
        
        folder_name = str(case_id).split("_")[0] if "_" in str(case_id) else str(case_id)
        folder_id = self.find_folder_in_drive(folder_name, parent_id=root_id)
        if not folder_id:
            folder_id = self.create_folder(folder_name, parent_id=root_id)
        
        new_doc_id = self.create_doc(doc_name, folder_id=folder_id)
        self.share_file(new_doc_id, customer_email)
        self.share_file(new_doc_id, ADMIN_EMAIL)
        return new_doc_id

    def upload_image_to_drive(self, image_file, filename, parent_id, folder_name="Images_圖檔"):
        """
        上傳圖片或 GIF 到 Drive。
        """
        try:
            images_folder_id = self.find_folder_in_drive(folder_name, parent_id=parent_id)
            if not images_folder_id:
                images_folder_id = self.create_folder(folder_name, parent_id=parent_id)
            
            image_file.seek(0)
            # 獲取正確的 MIME 類型 (例如 image/gif)
            mime_type = image_file.type if hasattr(image_file, 'type') else 'image/jpeg'
            
            file_metadata = {
                'name': filename,
                'parents': [images_folder_id]
            }
            media = MediaIoBaseUpload(image_file, mimetype=mime_type, resumable=True)
            
            new_file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink, thumbnailLink',
                supportsAllDrives=True
            ).execute()
            
            new_file_id = new_file.get('id')
            # 設定權限為任何人可讀 (Docs 插入圖片需要此權限)
            self.drive_service.permissions().create(
                fileId=new_file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            
            time.sleep(1) # 稍等權限生效
            
            thumb_link = new_file.get('thumbnailLink')
            if thumb_link:
                final_link = thumb_link.replace('=s220', '=s1600')
                return final_link, new_file.get('webContentLink')
            
            return new_file.get('webContentLink'), new_file.get('webContentLink')
        except Exception as e:
            st.warning(f"⚠️ 素材上傳失敗: {e}")
            return None, None

    def append_ad_data_to_doc(self, doc_id, ad_data, case_id):
        block_name = f"{ad_data.get('ad_name_id')}_{ad_data.get('image_name_id')}"
        
        try:
            doc_info = self.drive_service.files().get(fileId=doc_id, fields='parents', supportsAllDrives=True).execute()
            parent_id = doc_info.get('parents', [None])[0]
        except:
            parent_id = None

        # --- 素材上傳處理 ---
        image_file = ad_data.get('image_file')
        image_insert_link = None
        
        if image_file and parent_id:
            # 偵測副檔名並統一轉小寫
            original_ext = os.path.splitext(image_file.name)[1].lower()
            if not original_ext:
                # 根據 MIME type 補上副檔名
                mime = getattr(image_file, 'type', '')
                ext_map = {'image/gif': '.gif', 'image/png': '.png', 'image/jpeg': '.jpg'}
                original_ext = ext_map.get(mime, '.jpg')
            
            final_filename = f"{ad_data.get('image_name_id')}{original_ext}"
            customer_name = str(case_id).split("_")[0] if "_" in str(case_id) else str(case_id)
            target_folder_name = f"{customer_name}_img"

            st.sidebar.text(f"Debug: 上傳素材 '{final_filename}'...")
            thumb, web = self.upload_image_to_drive(image_file, final_filename, parent_id, folder_name=target_folder_name)
            
            ad_data['image_url'] = web
            image_insert_link = thumb
        
        # --- 寫入 Google Doc (Table Layout) ---
        requests_body = [{'insertTable': {'rows': 1, 'columns': 2, 'location': {'index': 1}}}]
        self.docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests_body}).execute()
        
        doc = self.docs_service.documents().get(documentId=doc_id).execute()
        content = doc.get('body').get('content')
        
        table = None
        for element in content:
            if 'table' in element:
                table = element['table']
                break
        
        if table:
            row = table['tableRows'][0]
            left_index = row['tableCells'][0]['content'][0]['startIndex']
            right_index = row['tableCells'][1]['content'][0]['startIndex']
            
            text_content = (
                f"廣告組合 ID: {block_name}\n"
                f"送出時間: {ad_data.get('fill_time')}\n"
                f"廣告名稱/編號: {ad_data.get('ad_name_id')}\n"
                f"對應圖片名稱/編號: {ad_data.get('image_name_id')}\n"
                f"素材雲端網址: {ad_data.get('image_url')}\n"
                f"廣告標題: {ad_data.get('headline')}\n"
                f"廣告到達網址: {ad_data.get('landing_url')}\n"
                f"廣告主文案:\n{ad_data.get('main_copy')}\n"
            )
            
            batch_requests = []
            if image_insert_link:
                batch_requests.append({
                    'insertInlineImage': {
                        'uri': image_insert_link,
                        'location': {'index': right_index},
                        'objectSize': {'width': {'magnitude': 150, 'unit': 'PT'}}
                    }
                })

            batch_requests.append({
                'insertText': {
                    'location': {'index': left_index},
                    'text': text_content
                }
            })
            self.docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': batch_requests}).execute()
        
        return block_name

    def send_confirmation_email(self, to_email, ad_data, doc_url):
        if self.auth_mode != "oauth":
            st.info("ℹ️ 目前為 Service Account 模式，跳過 Gmail 寄信。")
            return False
        try:
            service = build('gmail', 'v1', credentials=self.creds)
            body_text = f"廣告素材已成功提交！\n\n案號: {ad_data.get('case_id')}\n廣告名稱: {ad_data.get('ad_name_id')}\n素材連結: {ad_data.get('image_url')}\n文件連結: {doc_url}"
            message = MIMEText(body_text)
            message['to'] = to_email
            message['from'] = 'me'
            message['subject'] = f"✅ [{ad_data.get('case_id')}] 素材提交成功"
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            return True
        except Exception as e:
            st.error(f"⚠️ Email 寄送失敗: {e}")
            return False
