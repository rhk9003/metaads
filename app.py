
app.py



import streamlit as st
import datetime
from utils import GoogleServices
# Initialize Google Services
# We cache this to avoid re-authenticating on every re-run
# Determine if cached or not - removing cache for now
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
    # Debug: Print boolean evaluation
    # st.write(f"Debug Main: type(services)={type(services)}")
    # st.write(f"Debug Main: bool(services)={bool(services)}")
    # Check for service account
    if not services or isinstance(services, str):
        st.error(f"無法連接 Google 服務。")
        st.error(f"變數狀態: services={services}, type={type(services)}")
        if isinstance(services, str):
            st.error(f"錯誤詳情: {services}")
        
        if st.button("清除快取並重試"):
            st.cache_resource.clear()
            st.rerun()
            
        return
    # Sidebar Actions that require services (only if services exist)
    with st.sidebar:
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
                    st.info("查無檔案")
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
    # Session state initialization...
if __name__ == "__main__":
    main()
