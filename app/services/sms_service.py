import logging
from typing import Tuple, Optional
from flask import current_app

logger = logging.getLogger(__name__)

class BaseSMSProvider:
    """Base interface for SMS OTP delivery."""
    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        raise NotImplementedError

class ConsoleSMSProvider(BaseSMSProvider):
    """
    Default mock/development SMS provider.
    Logs OTP to console and application logger without requiring paid third-party SMS gateways.
    """
    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        logger.info(f"===> [SMS OTP DISPATCH] To: {phone_number} | Message: {message} <===")
        return True, "SMS sent successfully via developer provider."

class SMSService:
    """
    Modular SMS service abstraction supporting pluggable providers (Twilio, AWS SNS, Vonage, etc.).
    """
    _provider: BaseSMSProvider = ConsoleSMSProvider()

    @classmethod
    def set_provider(cls, provider: BaseSMSProvider):
        cls._provider = provider

    @classmethod
    def send_otp(cls, phone_number: str, otp_code: str, expiry_minutes: int = 10) -> Tuple[bool, str]:
        phone_clean = phone_number.strip()
        message = f"Your StockSense verification code is {otp_code}. It expires in {expiry_minutes} minutes."
        return cls._provider.send_sms(phone_clean, message)
