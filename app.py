import streamlit as st
import datetime
from utils import GoogleServices
# Initialize Google Services
# We cache this to avoid re-authenticating on every re-run
@st.cache_resource
def get_google_services():
    try:
        return GoogleServices()
    except FileNotFoundError:
        return None
    except Exception as e:
        return str(e)
def main():
    st.set_page_config(page_title="Meta 廣告上刊系統", page_icon="📝")
    
    st.title("Meta 廣告上刊資訊填寫")
    services = get_google_services()
    # Check for service account
    if not services or isinstance(services, str):
        st.error("無法連接 Google 服務。請確認 `service_account.json` 是否存在於目錄中。")
        if isinstance(services, str):
            st.error(f"錯誤詳情: {services}")
        return
    # Session state initialization
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'case_id' not in st.session_state:
        st.session_state.case_id = None
    if 'email' not in st.session_state:
        st.session_state.email = ""
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
                        st.session_state.step = 2
                        st.success(f"找到案件編號: {case_id}")
                        st.rerun()
                    else:
                        st.error("找不到此 Email 對應的案件編號，請確認 Email 是否正確或聯繫管理員。")
    # Step 2: Ad Information Form
    elif st.session_state.step == 2:
        st.header(f"Step 2: 填寫上刊資訊 (案件: {st.session_state.case_id})")
        
        with st.form("ad_submission_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                fill_time = st.text_input("填寫時間", value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                ad_name_id = st.text_input("廣告名稱/編號 (必填)")
                image_name_id = st.text_input("對應圖片名稱/編號 (必填)")
                headline = st.text_input("廣告標題")
            
            with col2:
                image_url = st.text_input("對應圖片雲端網址")
                landing_url = st.text_input("廣告到達網址")
                main_copy = st.text_area("廣告主文案", height=150)
            submitted = st.form_submit_button("送出並建立文件")
            
            if submitted:
                if not ad_name_id or not image_name_id:
                    st.error("請填寫 '廣告名稱/編號' 與 '對應圖片名稱/編號'")
                else:
                    try:
                        with st.spinner("處理中...建立/更新文件中..."):
                            # 1. Ensure Doc Exists and Share
                            doc_id = services.ensure_doc_exists_and_share(st.session_state.case_id, st.session_state.email)
                            
                            # 2. Prepare Data
                            ad_data = {
                                'fill_time': fill_time,
                                'ad_name_id': ad_name_id,
                                'image_name_id': image_name_id,
                                'image_url': image_url,
                                'headline': headline,
                                'main_copy': main_copy,
                                'landing_url': landing_url
                            }
                            
                            # 3. Append Logic
                            block_name = services.append_ad_data_to_doc(doc_id, ad_data)
                            
                        st.success(f"成功! 資料已寫入文件。")
                        st.info(f"產生的廣告組合名稱: {block_name}")
                        st.info(f"文件 ID: {doc_id} (已分享給您)")
                        
                        if st.button("填寫下一則"):
                            # Reset some fields if needed, or just stay here. 
                            # Streamlit form reset is implicit on rerun if keys match, but using forms keeps state.
                            # Just clearing manually if users want, or they can rewrite.
                            pass
                            
                    except Exception as e:
                        st.error(f"發生錯誤: {e}")
        if st.button("回上一步 (重新查詢)"):
            st.session_state.step = 1
            st.session_state.case_id = None
            st.rerun()
    with st.sidebar:
        st.subheader("管理員專區")
        if st.button("檢查雲端空間 & 檔案"):
            try:
                # 1. Check Quota
                about = services.drive_service.about().get(fields="storageQuota, user").execute()
                quota = about['storageQuota']
                limit = int(quota.get('limit', 0))
                usage = int(quota.get('usage', 0))
                trash = int(quota.get('usageInDriveTrash', 0))
                
                st.write(f"帳號: {about['user']['emailAddress']}")
                st.write(f"--- 配額資訊 ---")
                st.write(f"總容量限制: {limit} bytes ({limit / (1024**3):.4f} GB)")
                st.write(f"已使用: {usage} bytes ({usage / (1024**3):.4f} GB)")
                st.write(f"垃圾桶佔用: {trash} bytes")
                
                # 2. Check File Count
                st.write(f"--- 檔案列表 (前 20 筆) ---")
                results = services.drive_service.files().list(
                    q="'me' in owners and trashed = false",
                    pageSize=20,
                    fields="files(id, name, size, createdTime)"
                ).execute()
                files = results.get('files', [])
                
                if not files:
                    st.info("查無檔案 (此帳號目前沒有擁有任何檔案)")
                else:
                    for f in files:
                        f_size = f.get('size', '0')
                        st.text(f"[{f['createdTime']}] {f['name']} ({f_size} bytes)")
                        
                if trash > 0:
                     if st.button("清空垃圾桶"):
                        services.drive_service.files().emptyTrash().execute()
                        st.success("垃圾桶已清空！")
                        st.rerun()
            except Exception as e:
                st.error(f"查詢失敗: {e}")
if __name__ == "__main__":
    main()
