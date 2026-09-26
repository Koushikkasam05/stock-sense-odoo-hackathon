import logging
from typing import Optional
from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log_event(
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        role: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """
        Records an immutable audit log entry for security and compliance.
        """
        try:
            # Auto-populate user details from current_user if authenticated
            if user_id is None and current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
                role = current_user.role

            # Auto-populate client IP address from Flask request if available
            if ip_address is None and request:
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

            entry = AuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                details=details,
                user_id=user_id,
                username=username,
                role=role,
                ip_address=ip_address
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")
            db.session.rollback()
            return None
