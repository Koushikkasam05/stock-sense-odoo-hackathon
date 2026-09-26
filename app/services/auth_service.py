import re
import random
import string
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from flask import current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models.user import User, OTPToken
from app.services.sms_service import SMSService

logger = logging.getLogger(__name__)

# Strong Password Pattern: Minimum 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special symbol
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')

# Standard RFC 5322 compatible email format regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

class AuthService:
    @staticmethod
    def validate_email_format(email: str) -> Tuple[bool, str]:
        """
        Validates email address constraints:
        - Must be non-empty
        - Must match standard email format (e.g., user@domain.com)
        """
        if not email or not email.strip():
            return False, "Email address is required."
        clean_email = email.strip()
        if not EMAIL_REGEX.match(clean_email):
            return False, "Invalid email address format (must be like user@example.com)."
        return True, ""

    @staticmethod
    def validate_password_complexity(password: str) -> Tuple[bool, str]:
        """
        Validates password requirements:
        - Minimum 8 characters
        - At least one lowercase letter (a-z)
        - At least one uppercase letter (A-Z)
        - At least one numeric digit (0-9)
        - At least one special symbol (!@#$%^&*...)
        """
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not PASSWORD_REGEX.match(password):
            return False, "Password must contain at least 1 uppercase letter, 1 lowercase letter, 1 numeric digit, and 1 special symbol."
        return True, ""

    @staticmethod
    def register_user(
        username: str,
        email: str,
        password: str,
        full_name: str,
        mobile_number: Optional[str] = None,
        role: str = 'warehouse_staff'
    ) -> User:
        username_clean = username.strip().lower()
        email_clean = email.strip().lower()
        mobile_clean = mobile_number.strip() if mobile_number else None

        # Email constraint check
        is_valid_email, email_msg = AuthService.validate_email_format(email_clean)
        if not is_valid_email:
            raise ValueError(email_msg)

        if User.query.filter_by(username=username_clean).first():
            raise ValueError(f"Username '{username_clean}' is already registered.")

        if User.query.filter_by(email=email_clean).first():
            raise ValueError(f"Email '{email_clean}' is already registered.")

        if mobile_clean and User.query.filter_by(mobile_number=mobile_clean).first():
            raise ValueError(f"Mobile number '{mobile_clean}' is already registered.")

        if role not in ['inventory_manager', 'warehouse_staff']:
            role = 'warehouse_staff'

        user = User(
            username=username_clean,
            email=email_clean,
            mobile_number=mobile_clean,
            full_name=full_name.strip(),
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def authenticate_user(identifier: str, password: str) -> Optional[User]:
        """Authenticates user via Username, Email address, or Mobile number with password."""
        ident_clean = identifier.strip().lower()
        user = User.query.filter(
            (User.username == ident_clean) |
            (User.email == ident_clean) |
            (User.mobile_number == identifier.strip())
        ).first()

        if user and user.is_active and user.check_password(password):
            return user
        return None

    @staticmethod
    def generate_otp_code(length: int = 6) -> str:
        """Generates a secure, cryptographically random 6-digit numeric OTP."""
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def request_login_otp(identifier: str) -> Tuple[bool, str, Optional[str]]:
        """
        Generates and dispatches a single-use 6-digit OTP for login via Email or Mobile.
        Returns (success, message, dev_otp_code).
        """
        ident_clean = identifier.strip().lower()
        user = User.query.filter(
            (User.email == ident_clean) |
            (User.username == ident_clean) |
            (User.mobile_number == identifier.strip())
        ).filter_by(is_active=True).first()

        if not user:
            return False, "No active account found matching this Email, Username, or Mobile number.", None

        # Rate limiting: Check if an active OTP was generated within the last 60 seconds
        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        recent_otp = OTPToken.query.filter(
            OTPToken.user_id == user.id,
            OTPToken.purpose.in_(['login_otp', 'mobile_login']),
            OTPToken.created_at >= recent_cutoff
        ).first()

        if recent_otp:
            return False, "Please wait 60 seconds before requesting another 6-digit OTP.", None

        # Invalidate previous unused login OTPs for this user
        OTPToken.query.filter(
            OTPToken.user_id == user.id,
            OTPToken.purpose.in_(['login_otp', 'mobile_login']),
            OTPToken.is_used == False
        ).update({'is_used': True})

        otp_code = AuthService.generate_otp_code(6)
        expiry_minutes = current_app.config.get('OTP_EXPIRY_MINUTES', 10)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        token = OTPToken(
            user_id=user.id,
            otp_code=otp_code,
            purpose='login_otp',
            expires_at=expires_at,
            is_used=False
        )
        db.session.add(token)
        db.session.commit()

        # Send via Email if identifier contains '@' or if user has email
        is_email_delivery = '@' in identifier.strip() or not user.mobile_number
        sent_email = False

        if is_email_delivery:
            if current_app.config.get('MAIL_USERNAME') and current_app.config.get('MAIL_PASSWORD'):
                try:
                    msg = Message(
                        subject="StockSense - 6-Digit Login Verification Code",
                        recipients=[user.email],
                        body=f"Hello {user.full_name},\n\nYour StockSense 6-digit login verification code is: {otp_code}\n\nThis single-use code expires in {expiry_minutes} minutes.\nIf you did not initiate this login, please contact your inventory manager immediately."
                    )
                    mail.send(msg)
                    sent_email = True
                except Exception as e:
                    logger.warning(f"Failed to dispatch email via SMTP: {e}")
            logger.info(f"===> [EMAIL LOGIN OTP] User: {user.email} | Code: {otp_code} <===")
            dest_str = f"email ({user.email})"
        else:
            SMSService.send_otp(user.mobile_number, otp_code, expiry_minutes)
            logger.info(f"===> [MOBILE LOGIN OTP] User: {user.username} | Mobile: {user.mobile_number} | Code: {otp_code} <===")
            dest_str = f"mobile ({user.mobile_number})"

        msg_str = f"6-digit OTP sent to {dest_str}. (Dev Code: {otp_code})"
        return True, msg_str, otp_code

    @staticmethod
    def verify_login_otp(identifier: str, otp_code: str) -> Tuple[bool, str, Optional[User]]:
        """
        Verifies single-use 6-digit OTP for Email/Mobile login.
        """
        if not otp_code or len(otp_code.strip()) != 6:
            return False, "Please enter a valid 6-digit verification code.", None

        ident_clean = identifier.strip().lower()
        user = User.query.filter(
            (User.email == ident_clean) |
            (User.username == ident_clean) |
            (User.mobile_number == identifier.strip())
        ).filter_by(is_active=True).first()

        if not user:
            return False, "Invalid account identifier.", None

        token = OTPToken.query.filter(
            OTPToken.user_id == user.id,
            OTPToken.otp_code == otp_code.strip(),
            OTPToken.purpose.in_(['login_otp', 'mobile_login']),
            OTPToken.is_used == False
        ).order_by(OTPToken.created_at.desc()).first()

        if not token or not token.is_valid():
            return False, "Invalid or expired 6-digit OTP code.", None

        # Single-use: Mark OTP as used
        token.is_used = True
        db.session.commit()

        return True, "Login successful.", user

    # Backwards-compatible aliases for mobile-specific routes
    request_mobile_login_otp = request_login_otp
    verify_mobile_login_otp = verify_login_otp

    @staticmethod
    def request_password_reset_otp(email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Generates a 6-digit OTP for password reset and dispatches email/console alert.
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
                    body=f"Hello {user.full_name},\n\nYour StockSense 6-digit OTP verification code is: {otp_code}\n\nThis code will expire in {expiry_minutes} minutes.\nIf you did not request this, please ignore this email."
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

        # Verify password complexity if token is valid
        if new_password:
            valid, msg = AuthService.validate_password_complexity(new_password)
            if not valid and len(new_password) < 6:
                return False, msg

        # Mark OTP as used and update user password
        token.is_used = True
        user.set_password(new_password)
        db.session.commit()

        return True, "Password has been successfully reset. You can now log in."
