import streamlit as st
from datetime import datetime, timedelta
from services.document_utils import generate_docx_bytes

def render_stage1(client_name, client_email):
    st.header("第一階段｜合約")
    
    st.info("""
    💡 **操作流程**：
    1. **確認資訊**：系統已自動帶入您的名稱與信箱。
    2. **選擇方案**：選擇付款方案與日期。
    3. **生成合約**：點擊生成按鈕預覽合約。
    4. **確認提交**：確認無誤後，點擊「完成並送出」，系統將產生案件號並通知服務方。
    """)

    # Constants
    PROVIDER_NAME = "高如慧"
    BANK_NAME = "中國信託商業銀行"
    BANK_CODE = "822"
    ACCOUNT_NUMBER = "783540208870"

    # Form
    st.subheader("💰 付款方案")
    payment_option = st.radio(
        "方案選擇：",
        options=["17,000元/月（每月付款）", "45,000元/三個月（一次付款）"],
        index=0
    )

    st.subheader("📅 時間設定")
    default_start = datetime.now().date() + timedelta(days=7)
    start_date = st.date_input("合作啟動日", value=default_start, min_value=datetime.now().date())

    payment_day = None
    payment_date = None

    if payment_option == "17,000元/月（每月付款）":
        payment_day = st.slider("每月付款日", 1, 28, 5)
    else:
        default_pay = start_date - timedelta(days=3)
        if default_pay < datetime.now().date():
            default_pay = datetime.now().date()
        payment_date = st.date_input("付款日期", value=default_pay, min_value=datetime.now().date(), max_value=start_date)

    st.markdown("---")
    st.subheader("🧾 甲方資訊")
    st.text_input("甲方名稱", value=client_name, disabled=True)
    st.text_input("甲方信箱", value=client_email, disabled=True)

    # Generate Case ID
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = "".join([c for c in client_name if c.isalnum() or c in (" ", "_", "-")]).strip()
    case_id = f"{safe_name}_{date_str}"
    
    st.caption(f"預計案件編號：{case_id}")

    st.markdown("---")
    
    if st.button("📝 生成 Word 合約預覽", type="primary"):
        docx_bytes = generate_docx_bytes(
            party_a=client_name,
            email=client_email,
            payment_opt=payment_option,
            start_dt=start_date,
            pay_day=payment_day,
            pay_dt=payment_date,
            case_num=case_id,
            provider_name=PROVIDER_NAME,
            bank_name=BANK_NAME,
            bank_code=BANK_CODE,
            account_number=ACCOUNT_NUMBER
        )
        
        # Save to session state for download
        st.session_state['stage1_docx'] = docx_bytes
        
        # Data preparation matching Google Sheet Columns
        st.session_state['stage1_data'] = {
            "case_id": case_id,
            "party_a": client_name,
            "Email": client_email,
            "provider": PROVIDER_NAME,
            "plan": payment_option,
            "plan_raw": payment_option,
            "start_date": str(start_date),
            "pay_day": str(payment_day) if payment_day else "",
            "pay_date": str(payment_date) if payment_date else "",
            "Status": "Stage1_Done"
        }
        st.success("合約已生成，請確認下方資訊並提交。")

    if 'stage1_docx' in st.session_state:
        st.download_button(
            label="⬇️ 下載 Word 合約 (.docx)",
            data=st.session_state['stage1_docx'],
            file_name=f"廣告投放合約_{case_id}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        st.markdown("### 確認並提交")
        st.warning("請確認已下載合約。提交後將會通知服務方。")
        
        if st.button("✅ 完成並送出 (建立案件)", type="primary"):
            return st.session_state['stage1_data']

    return None
