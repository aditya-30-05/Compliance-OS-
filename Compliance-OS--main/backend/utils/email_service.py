"""
Email service for ComplianceOS.
Supports SMTP (Resend/SendGrid/Manual) with HTML templates.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.config import settings
from backend.utils.logger import logger

try:
    import resend
    # Use SMTP_PASSWORD if it looks like a Resend key (starts with re_)
    if settings.SMTP_PASSWORD and settings.SMTP_PASSWORD.startswith("re_"):
        resend.api_key = settings.SMTP_PASSWORD
        HAS_RESEND = True
    else:
        HAS_RESEND = False
except ImportError:
    HAS_RESEND = False

def send_email(to_email: str, subject: str, html_content: str):
    """Send an HTML email via Resend SDK or SMTP."""
    if not settings.ENABLE_EMAIL:
        logger.warning(f"Email disabled. Would have sent to {to_email}: {subject}")
        return

    if HAS_RESEND:
        try:
            resend.Emails.send({
                "from": settings.EMAIL_FROM,
                "to": to_email,
                "subject": f"{settings.APP_NAME} — {subject}",
                "html": html_content
            })
            logger.info(f"Email sent via Resend to {to_email}: {subject}")
            return
        except Exception as e:
            logger.error(f"Resend failed, falling back to SMTP: {e}")

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email
        msg["Subject"] = f"{settings.APP_NAME} — {subject}"

        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent via SMTP to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")

def send_welcome_email(to_email: str, name: str):
    subject = "Welcome to ComplianceOS"
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border: 1px solid #e2e8f0; border-radius: 12px; color: #1e293b;">
        <h1 style="color: #3b82f6; margin-bottom: 24px;">Welcome to ComplianceOS</h1>
        <p style="font-size: 16px; line-height: 1.6;">Hello {name},</p>
        <p style="font-size: 16px; line-height: 1.6;">Your multi-agent regulatory intelligence dashboard is ready. ComplianceOS uses a chain of specialized AI agents to analyze complex regulations in seconds.</p>
        <div style="margin: 32px 0;">
            <a href="https://complianceos.com/login" style="background: linear-gradient(135deg,#3b82f6,#8b5cf6); color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 700; display: inline-block;">Get Started Now</a>
        </div>
        <p style="font-size: 14px; color: #64748b;">If you didn't sign up for this account, you can safely ignore this email.</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 32px 0;"/>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">&copy; 2024 ComplianceOS. Built for Enterprise Scale.</p>
    </div>
    """
    send_email(to_email, subject, html)

def send_password_reset_email(to_email: str, token: str):
    reset_link = f"https://complianceos.com/reset-password.html?token={token}"
    subject = "Reset Your Password"
    html = f"""
    <div style="font-family: 'Inter', sans-serif; max-width: 600px; margin: 0 auto; padding: 40px; border: 1px solid #e2e8f0; border-radius: 12px; color: #1e293b;">
        <h1 style="color: #ef4444; margin-bottom: 24px;">Password Reset</h1>
        <p style="font-size: 16px; line-height: 1.6;">We received a request to reset your password for your ComplianceOS account. Click the button below to set a new password:</p>
        <div style="margin: 32px 0;">
            <a href="{reset_link}" style="background: #0f172a; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 700; display: inline-block;">Reset Password</a>
        </div>
        <p style="font-size: 14px; color: #64748b;">This link will expire in 15 minutes. If you did not request a password reset, no further action is required.</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 32px 0;"/>
        <p style="font-size: 12px; color: #94a3b8; text-align: center;">&copy; 2024 ComplianceOS. Security first.</p>
    </div>
    """
    send_email(to_email, subject, html)
