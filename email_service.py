import smtplib
from email.mime.text import MIMEText
from email.header import Header
import streamlit as st

class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        # Credentials should be in secrets
        # [email]
        # sender = "..."
        # password = "..."
        self.sender = st.secrets["email"]["sender"] if "email" in st.secrets else None
        self.password = st.secrets["email"]["password"] if "email" in st.secrets else None

    def send_notification(self, subject, body, to_emails):
        if not self.sender or not self.password:
            st.warning("Email credentials not configured properly.")
            return False

        if isinstance(to_emails, str):
            to_emails = [to_emails]

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = self.sender
        msg['To'] = ", ".join(to_emails)

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender, self.password)
            server.sendmail(self.sender, to_emails, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            st.error(f"Failed to send email: {e}")
            return False

def send_update_notification(user_name, action, details=""):
    email_service = EmailService()
    subject = f"【系統通知】{user_name} 已完成 {action}"
    body = f"""
    系統通知：
    
    用戶：{user_name}
    動作：{action}
    
    詳細內容：
    {details}
    
    請查收。
    """
    # Send to admin
    admin_email = "rhk9903@gmail.com"
    email_service.send_notification(subject, body, [admin_email])
