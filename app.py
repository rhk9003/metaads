import streamlit as st
import datetime
from utils import GoogleServices

def get_google_services():
    try:
        instance = GoogleServices()
        return instance
    except Exception as e:
        st.sidebar.error(f"Debug: Init Exception: {e}")
        return str(e)

def main():
    st.set_page_config(page_title="Meta 廣告批次上刊系統", page_icon="📝", layout="wide")
    
    st.title("Meta 廣告上刊資訊填寫 (批次模式)")
    services = get_google_services()

    # --- 初始化 Session State ---
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'case_id' not in st.session_state: st.session_state.case_id = None
    if 'email' not in st.session_state: st.session_state.email = ""
    if 'doc_id' not in st.session_state: st.session_state.doc_id = None
    # 儲存待上傳廣告的清單
    if 'ad_queue' not in st.session_state: st.session_state.ad_queue = []

    # 驗證失敗處理
    if not services or isinstance(services, str):
        st.error("無法連接 Google 服務，請檢查金鑰。")
        return

    # --- Step 1: 身份驗證 ---
    if st.session_state.step == 1:
        st.header("Step 1: 身份驗證")
        email_input = st.text_input("請輸入您的 Email")
        if st.button("查詢案件編號"):
            with st.spinner("查詢中..."):
                case_id = services.get_case_id_by_email(email_input)
                if case_id:
                    st.session_state.case_id = case_id
                    st.session_state.email = email_input
                    st.session_state.doc_id = services.ensure_doc_exists_and_share(case_id, email_input)
                    st.session_state.step = 2
                    st.rerun()
                else:
                    st.error("找不到此 Email 對應的案件，請聯繫管理員。")

    # --- Step 2: 填寫與清單管理 ---
    elif st.session_state.step == 2:
        st.header(f"Step 2: 編輯廣告清單 (案號: {st.session_state.case_id})")
        
        # A. 填寫區域
        with st.expander("➕ 新增廣告素材", expanded=len(st.session_state.ad_queue) == 0):
            with st.form("ad_entry_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    ad_name = st.text_input("廣告名稱/編號 (例如: A01)")
                    img_id = st.text_input("圖片名稱/編號 (例如: Pic_01)")
                    headline = st.text_input("廣告標題")
                with col2:
                    image_file = st.file_uploader("上傳素材 (JPG/PNG/GIF)", type=['png', 'jpg', 'jpeg', 'gif'])
                    landing_url = st.text_input("到達網址")
                
                main_copy = st.text_area("廣告主文案")
                
                add_to_list = st.form_submit_button("暫存至清單")
                if add_to_list:
                    if not ad_name or not image_file:
                        st.error("名稱與圖片為必填！")
                    else:
                        # 將資料存入 session_state 清單
                        new_ad = {
                            "ad_name_id": ad_name,
                            "image_name_id": img_id,
                            "image_file": image_file, # 這是原始檔案物件
                            "headline": headline,
                            "landing_url": landing_url,
                            "main_copy": main_copy,
                            "fill_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state.ad_queue.append(new_ad)
                        st.success(f"已加入清單！目前共有 {len(st.session_state.ad_queue)} 則。")
                        st.rerun()

        # B. 清單預覽與批次上傳
        if st.session_state.ad_queue:
            st.write("---")
            st.subheader(f"待上傳清單 ({len(st.session_state.ad_queue)})")
            
            # 使用表格或清單顯示
            for idx, ad in enumerate(st.session_state.ad_queue):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 4, 1])
                    c1.write(f"**{ad['ad_name_id']}**")
                    c1.write(f"📄 {ad['image_name_id']}")
                    c2.text(f"文案預覽: {ad['main_copy'][:50]}...")
                    if c3.button("移除", key=f"remove_{idx}"):
                        st.session_state.ad_queue.pop(idx)
                        st.rerun()

            st.write("---")
            col_btn1, col_btn2 = st.columns([1, 4])
            
            if col_btn1.button("🚀 開始批次上傳", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total = len(st.session_state.ad_queue)
                
                doc_url = f"https://docs.google.com/document/d/{st.session_state.doc_id}/edit"
                
                success_count = 0
                for i, ad_data in enumerate(st.session_state.ad_queue):
                    status_text.text(f"正在處理第 {i+1}/{total} 則: {ad_data['ad_name_id']}...")
                    try:
                        # 調用原本的 utils 邏輯
                        services.append_ad_data_to_doc(st.session_state.doc_id, ad_data, st.session_state.case_id)
                        success_count += 1
                    except Exception as e:
                        st.error(f"{ad_data['ad_name_id']} 上傳失敗: {e}")
                    
                    progress_bar.progress((i + 1) / total)
                
                status_text.success(f"完成！成功處理 {success_count} 則廣告。")
                
                # 發送一封總結通知信
                try:
                    services.send_confirmation_email(st.session_state.email, {"case_id": st.session_state.case_id, "ad_name_id": f"批次上傳({success_count}則)", "fill_time": "已完成"}, doc_url)
                except:
                    pass

                # 清空清單
                st.session_state.ad_queue = []
                st.balloons()
            
            if col_btn2.button("清空所有清單"):
                st.session_state.ad_queue = []
                st.rerun()

        if st.button("回上一步 (重新查詢)"):
            st.session_state.step = 1
            st.session_state.ad_queue = []
            st.rerun()

if __name__ == "__main__":
    main()
