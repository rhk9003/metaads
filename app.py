import streamlit as st
import datetime
from utils import GoogleServices

# Initialize Google Services
def get_google_services():
    try:
        instance = GoogleServices()
        st.sidebar.write(f"Debug: Service Instance Created: {type(instance)}")
        return instance
    except Exception as e:
        import traceback
        st.sidebar.error(f"Debug: Init Exception: {e}")
        st.sidebar.text(traceback.format_exc())
        return str(e)

def main():
    st.set_page_config(page_title="Meta 廣告上刊系統", page_icon="📝")
    
    # --- Sidebar (Always show for debugging) ---
    with st.sidebar:
        st.subheader("管理員專區")
        
        # Secrets Diagnostic
        st.write("--- Secrets 診斷 ---")
        if hasattr(st, 'secrets'):
            keys = list(st.secrets.keys())
            st.write(f"偵測到的 Keys: {keys}")
            
            if "gcp_service_account" in st.secrets:
                st.success("✅ [gcp_service_account] 存在")
            elif "gcp_json" in st.secrets:
                st.success("✅ gcp_json 存在")
            elif "private_key" in st.secrets:
                st.success("✅ private_key (Root) 存在")
            else:
                st.error("❌ 未偵測到有效金鑰")
        else:
            st.error("❌ st.secrets 無法讀取")
            
        st.write("---")

    st.title("Meta 廣告上刊資訊填寫")
    services = get_google_services()

    if not services or isinstance(services, str):
        st.error(f"無法連接 Google 服務。")
        st.error(f"變數狀態: services={services}, type={type(services)}")
        if isinstance(services, str):
            st.error(f"錯誤詳情: {services}")
        
        if st.button("清除快取並重試"):
            st.cache_resource.clear()
            st.rerun()
        return

    with st.sidebar:
        if st.button("檢查雲端空間 & 檔案"):
            try:
                about = services.drive_service.about().get(fields="storageQuota, user").execute()
                quota = about['storageQuota']
                limit = int(quota.get('limit', 0))
                usage = int(quota.get('usage', 0))
                trash = int(quota.get('usageInDriveTrash', 0))
                
                st.write(f"帳號: {about['user']['emailAddress']}")
                st.write(f"--- 配額資訊 ---")
                st.write(f"總容量限制: {limit / (1024**3):.4f} GB")
                st.write(f"已使用: {usage / (1024**3):.4f} GB")
                
                results = services.drive_service.files().list(
                    q="'me' in owners and trashed = false",
                    pageSize=20,
                    fields="files(id, name, size, createdTime)"
                ).execute()
                files = results.get('files', [])
                
                if not files:
                    st.info("查無檔案")
                else:
                    for f in files:
                        st.text(f"[{f['createdTime']}] {f['name']}")
                        
                if trash > 0:
                     if st.button("清空垃圾桶"):
                        services.drive_service.files().emptyTrash().execute()
                        st.success("垃圾桶已清空！")
                        st.rerun()
            except Exception as e:
                st.error(f"查詢失敗: {e}")

    # Session state initialization
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'case_id' not in st.session_state:
        st.session_state.case_id = None
    if 'email' not in st.session_state:
        st.session_state.email = ""
    if 'doc_id' not in st.session_state:
        st.session_state.doc_id = None

    # Step 1: Email Verification
    if st.session_state.step == 1:
        st.header("Step 1: 身份驗證")
        email_input = st.text_input("請輸入您的 Email", value=st.session_state.email)
        
        if st.button("查詢案件編號"):
            if not email_input:
                st.warning("請輸入 Email")
            else:
                with st.spinner("查詢中..."):
                    case_id = services.get_case_id_by_email(email_input)
                    if case_id:
                        st.session_state.case_id = case_id
                        st.session_state.email = email_input
                        try:
                            with st.spinner("正在確認雲端共享文件..."):
                                doc_id = services.ensure_doc_exists_and_share(case_id, email_input)
                                st.session_state.doc_id = doc_id
                        except Exception as e:
                            st.error(f"建立文件失敗: {e}")
                        
                        st.session_state.step = 2
                        st.success(f"找到案件編號: {case_id}")
                        st.rerun()
                    else:
                        st.error("找不到此 Email 對應的案件編號。")

    # Step 2: Ad Information Form
    elif st.session_state.step == 2:
        st.header(f"Step 2: 填寫上刊資訊 (案件: {st.session_state.case_id})")
        
        with st.form("ad_submission_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                ad_name_id = st.text_input("廣告名稱/編號 (必填)")
                image_name_id = st.text_input("對應圖片名稱/編號 (必填)")
                headline = st.text_input("廣告標題")
            
            with col2:
                # 修改處：加入 'gif' 到支援類型
                image_file = st.file_uploader("上傳廣告素材 (必填)", type=['png', 'jpg', 'jpeg', 'gif'])
                landing_url = st.text_input("廣告到達網址")
                main_copy = st.text_area("廣告主文案", height=150)
            
            submitted = st.form_submit_button("送出並建立文件")
            
            if submitted:
                if not ad_name_id or not image_name_id:
                    st.error("請填寫 '廣告名稱/編號' 與 '對應圖片名稱/編號'")
                elif not image_file:
                    st.error("請上傳廣告圖片或 GIF")
                else:
                    try:
                        with st.spinner("處理中...建立/更新文件中..."):
                            doc_id = st.session_state.doc_id
                            if not doc_id:
                                doc_id = services.ensure_doc_exists_and_share(st.session_state.case_id, st.session_state.email)
                                st.session_state.doc_id = doc_id
                            
                            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ad_data = {
                                'fill_time': current_time,
                                'ad_name_id': ad_name_id,
                                'image_name_id': image_name_id,
                                'image_file': image_file, 
                                'headline': headline,
                                'main_copy': main_copy,
                                'landing_url': landing_url,
                                'case_id': st.session_state.case_id
                            }
                            
                            block_name = services.append_ad_data_to_doc(doc_id, ad_data, st.session_state.case_id)
                            
                        st.success(f"成功! 資料已寫入文件。")
                        st.info(f"產生的廣告組合名稱: {block_name}")
                        
                        # Email Notification
                        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
                        admin_email = "rhk9903@gmail.com"
                        
                        try:
                            st.info("📨 正在寄送確認信...")
                            services.send_confirmation_email(st.session_state.email, ad_data, doc_url)
                            if st.session_state.email != admin_email:
                                services.send_confirmation_email(admin_email, ad_data, doc_url)
                            st.success(f"✅ 確認信已寄出！")
                        except Exception as e:
                            st.error(f"信件寄送失敗，但資料已存檔。錯誤: {e}")
                            
                    except Exception as e:
                        st.error(f"發生錯誤: {e}")

        if st.button("回上一步 (重新查詢)"):
            st.session_state.step = 1
            st.session_state.case_id = None
            st.rerun()

if __name__ == "__main__":
    main()
