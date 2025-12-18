import streamlit as st
from services.google_sheet import get_sheet_service
from services.email_service import send_update_notification
from views.stage1 import render_stage1
from views.stage2 import render_stage2
import time

st.set_page_config(
    page_title="廣告投放服務系統",
    page_icon="📝",
    layout="centered"
)

# Initialize Session State
if 'user_data' not in st.session_state:
    st.session_state['user_data'] = None
if 'auth_mode' not in st.session_state:
    st.session_state['auth_mode'] = None # 'register' or 'login'

def main():
    st.title("📝 廣告投放服務系統")

    # Sidebar Navigation
    with st.sidebar:
        st.header("功能選單")
        
        # If logged in, show user info and logout
        if st.session_state['user_data']:
            # Use safe get just in case
            name = st.session_state['user_data'].get('party_a') or st.session_state['user_data'].get('ClientName')
            st.success(f"Hi, {name}")
            if st.button("登出"):
                st.session_state['user_data'] = None
                st.session_state['auth_mode'] = None
                st.rerun()
        else:
            mode = st.radio("請選擇功能", ["建檔 (New Registration)", "登入 (Login)"])
            if "建檔" in mode:
                st.session_state['auth_mode'] = 'register'
            else:
                st.session_state['auth_mode'] = 'login'

    # Main Area Logic
    if not st.session_state['user_data']:
        if st.session_state['auth_mode'] == 'register':
            handle_register()
        else:
            handle_login()
    else:
        # User is logged in
        user = st.session_state['user_data']
        
        # Check status to determine view
        # We check keys for Stage 1 completion
        if user.get("Status") == "Stage1_Done" or user.get("Status") == "Stage2_Done" or user.get("case_id"):
             # Existing user with Case ID means Stage 1 is largely done
             handle_stage2_flow(user)
        else:
             # Fresh user
             handle_stage1_flow(user)

def handle_register():
    st.subheader("🆕 客戶建檔")
    with st.form("register_form"):
        name = st.text_input("客戶名稱 (Client Name)")
        email = st.text_input("聯絡信箱 (Google Email)")
        submitted = st.form_submit_button("開始建檔")
        
        if submitted:
            if not name or not email:
                st.error("請填寫所有欄位")
            elif "gmail.com" not in email.lower() and "google" not in email.lower():
                st.error("必須使用 Google 信箱 (Gmail) 才能使用此服務。")
                return
            
            # Check if user already exists?
            sheet = get_sheet_service()
            existing = sheet.get_user_by_email(email)
            if existing:
                st.error("此信箱已註冊，請直接登入。")
            else:
                # Set session state as "New User"
                st.session_state['user_data'] = {
                    "party_a": name,
                    "Email": email,
                    "Status": "New"
                }
                st.rerun()

def handle_login():
    st.subheader("🔑 客戶登入")
    with st.form("login_form"):
        email = st.text_input("聯絡信箱 (Google Email)")
        password = st.text_input("密碼", type="password")
        submitted = st.form_submit_button("登入")
        
        if submitted:
            if password != "dennis":
                st.error("密碼錯誤")
                return
            
            sheet = get_sheet_service()
            user = sheet.get_user_by_email(email)
            
            if user:
                st.session_state['user_data'] = user
                st.success("登入成功！")
                time.sleep(1)
                st.rerun()
            else:
                st.error("找不到此信箱的資料，請先建檔。")

def handle_stage1_flow(user):
    # Render Stage 1 View
    # returns data if submitted
    results = render_stage1(user.get('party_a'), user.get('Email'))
    
    if results:
        # Saving Logic
        status_msg = st.empty()
        status_msg.info("正在儲存資料...")
        
        # Merge results into user data
        user.update(results)
        
        # Save to Google Sheet
        sheet = get_sheet_service()
        success = sheet.create_or_update_user(user)
        
        if success:
            send_update_notification(user.get('party_a'), "第一階段｜合約", f"案件號：{user.get('case_id')}")
            status_msg.success("資料已儲存！已通知服務方。")
            # Update session state status
            st.session_state['user_data'] = user
            time.sleep(2)
            st.rerun()
        else:
            status_msg.error("儲存失敗，請檢查網路或聯絡管理員。")

def handle_stage2_flow(user):
    # Render Stage 2 View
    updates = render_stage2(user)
    
    if updates:
        # Saving Logic
        status_msg = st.empty()
        status_msg.info("正在更新資料...")
        
        user.update(updates)
        
        sheet = get_sheet_service()
        success = sheet.create_or_update_user(user)
        
        if success:
            send_update_notification(user.get('party_a'), "第二階段｜啟動前確認", f"更新欄位：{list(updates.keys())}")
            status_msg.success("更新成功！")
            st.session_state['user_data'] = user
            time.sleep(1)
            st.rerun()
        else:
            status_msg.error("更新失敗。")

if __name__ == "__main__":
    main()
