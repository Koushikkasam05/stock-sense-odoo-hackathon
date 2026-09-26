import random
import string
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from flask import current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models.user import User, OTPToken

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def register_user(username: str, email: str, password: str, full_name: str, role: str = 'warehouse_staff') -> User:
        username_clean = username.strip().lower()
        email_clean = email.strip().lower()

        if User.query.filter_by(username=username_clean).first():
            raise ValueError(f"Username '{username_clean}' is already registered.")

        if User.query.filter_by(email=email_clean).first():
            raise ValueError(f"Email '{email_clean}' is already registered.")

        if role not in ['inventory_manager', 'warehouse_staff']:
            role = 'warehouse_staff'

        user = User(
            username=username_clean,
            email=email_clean,
            full_name=full_name.strip(),
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def authenticate_user(username_or_email: str, password: str) -> Optional[User]:
        identifier = username_or_email.strip().lower()
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.is_active and user.check_password(password):
            return user
        return None

    @staticmethod
    def generate_otp_code(length: int = 6) -> str:
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def request_password_reset_otp(email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Generates an OTP for password reset and dispatches email/console alert.
        Returns (success, message, otp_code_for_dev).
        """
        email_clean = email.strip().lower()
        user = User.query.filter_by(email=email_clean).first()
        if not user:
            return False, "No account found with this email address.", None

        # Invalidate old OTPs
        OTPToken.query.filter_by(user_id=user.id, purpose='password_reset', is_used=False).update({'is_used': True})

        otp_code = AuthService.generate_otp_code(6)
        expiry_minutes = current_app.config.get('OTP_EXPIRY_MINUTES', 10)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        token = OTPToken(
            user_id=user.id,
            otp_code=otp_code,
            purpose='password_reset',
            expires_at=expires_at,
            is_used=False
        )
        db.session.add(token)
        db.session.commit()

        # Send via Flask-Mail or fallback to console log
        sent_email = False
        if current_app.config.get('MAIL_USERNAME') and current_app.config.get('MAIL_PASSWORD'):
            try:
                msg = Message(
                    subject="StockSense - Password Reset Verification Code",
                    recipients=[user.email],
                    body=f"Hello {user.full_name},\n\nYour StockSense OTP verification code is: {otp_code}\n\nThis code will expire in {expiry_minutes} minutes.\nIf you did not request this, please ignore this email."
                )
                mail.send(msg)
                sent_email = True
            except Exception as e:
                logger.warning(f"Failed to send email via SMTP: {e}")

        logger.info(f"===> [STOCKSENSE OTP] User: {user.email} | OTP Code: {otp_code} <===")
        msg_str = "Password reset OTP sent to your email." if sent_email else f"Password reset OTP generated. (Dev Mode: {otp_code})"
        return True, msg_str, otp_code

    @staticmethod
    def verify_and_reset_password(email: str, otp_code: str, new_password: str) -> Tuple[bool, str]:
        email_clean = email.strip().lower()
        user = User.query.filter_by(email=email_clean).first()
        if not user:
            return False, "Invalid email address."

        token = OTPToken.query.filter_by(
            user_id=user.id,
            otp_code=otp_code.strip(),
            purpose='password_reset',
            is_used=False
        ).order_by(OTPToken.created_at.desc()).first()

        if not token or not token.is_valid():
            return False, "Invalid or expired OTP code."

        # Mark OTP as used and update user password
        token.is_used = True
        user.set_password(new_password)
        db.session.commit()

        return True, "Password has been successfully reset. You can now log in."
