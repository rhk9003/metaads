import streamlit as st

def render_stage2(sheet_data):
    st.header("第二階段｜啟動前確認")

    # Show Stage 1 Info
    st.info(f"""
    **案件資訊 (第一階段已鎖定)**
    - 案件編號：{sheet_data.get('case_id')}
    - 客戶名稱：{sheet_data.get('party_a')}
    - 方案：{sheet_data.get('plan')}
    - 啟動日：{sheet_data.get('start_date')}
    """)

    st.subheader("✅ 確認事項（照實勾選）")
    
    # Helper to safe get boolean
    def get_bool(key):
        val = sheet_data.get(key)
        if isinstance(val, str):
            return val.lower() == 'true'
        return bool(val)

    with st.form("stage2_form"):
        col1, col2 = st.columns(2)
        with col1:
            chk_ad_account = st.checkbox("廣告帳號已開啟", value=get_bool("chk_ad_account"))
            chk_pixel = st.checkbox("像素事件已埋放", value=get_bool("chk_pixel"))
        with col2:
            chk_fanpage = st.checkbox("粉專已建立", value=get_bool("chk_fanpage"))
            chk_bm = st.checkbox("企業管理平台已建立", value=get_bool("chk_bm"))

        st.markdown("**遠端操作配合**")
        # Assuming remote ready is NOT in the user prompt column list explicitly, 
        # but user said "Already filled Stage 2...". 
        # The prompt listed: Email case_id party_a provider plan start_date pay_day pay_date chk_ad_account chk_pixel chk_fanpage chk_bm fanpage_url landing_url comp1 comp2 comp3 who_problem what_problem how_solve budget last_update_at msg_type plan_raw display_label
        # I do not see "RemoteReady" or "MaterialUploaded" in the list.
        # I will keep them if they are useful or remove them if strictly following that list.
        # The list seems comprehensive. I'll stick to the list provided by the user.
        # There is no RemoteReady column in the user's list. 
        # Maybe I should drop it or map it to something?
        # I will drop it to be safe 
        
        st.markdown("**廣告素材刊登**")
        st.info("請前往 [廣告素材刊登系統](https://metaads-dtwbm3ntmprhjvpv6ptmec.streamlit.app/) 完成素材上傳。")
        
        st.subheader("🧾 須提供事項")
        fanpage_url = st.text_input("粉專網址", value=sheet_data.get("fanpage_url", ""))
        landing_url = st.text_input("廣告導向頁", value=sheet_data.get("landing_url", ""))

        st.markdown("**競爭對手粉專**")
        comp1 = st.text_input("競品 1", value=sheet_data.get("comp1", ""))
        comp2 = st.text_input("競品 2", value=sheet_data.get("comp2", ""))
        comp3 = st.text_input("競品 3", value=sheet_data.get("comp3", ""))

        who_problem = st.text_area("解決誰的問題？", value=sheet_data.get("who_problem", ""))
        what_problem = st.text_area("要解決什麼問題？", value=sheet_data.get("what_problem", ""))
        how_solve = st.text_area("如何解決？", value=sheet_data.get("how_solve", ""))
        budget = st.text_input("第一個月預算", value=sheet_data.get("budget", ""))

        submitted = st.form_submit_button("💾 儲存並更新資料")
        
        if submitted:
            # Gather data
            updated_data = {
                "chk_ad_account": chk_ad_account,
                "chk_pixel": chk_pixel,
                "chk_fanpage": chk_fanpage,
                "chk_bm": chk_bm,
                "fanpage_url": fanpage_url,
                "landing_url": landing_url,
                "comp1": comp1,
                "comp2": comp2,
                "comp3": comp3,
                "who_problem": who_problem,
                "what_problem": what_problem,
                "how_solve": how_solve,
                "budget": budget,
                "Status": "Stage2_Done"
            }
            return updated_data
            
    return None
