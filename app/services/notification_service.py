from typing import List, Optional
from datetime import datetime, timezone
from app.extensions import db
from app.models.notification import Notification

class NotificationService:
    @staticmethod
    def create_notification(
        title: str,
        message: str,
        notification_type: str = 'info',
        user_id: Optional[int] = None
    ) -> Notification:
        """Creates an in-app notification without duplicating exact pending alerts."""
        # Avoid creating duplicate unread notifications for the same title/message
        existing = Notification.query.filter_by(
            user_id=user_id,
            title=title,
            is_read=False
        ).first()

        if existing:
            return existing

        notif = Notification(
            user_id=user_id,
            title=title.strip(),
            message=message.strip(),
            notification_type=notification_type,
            is_read=False,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notif)
        db.session.commit()
        return notif

    @staticmethod
    def get_user_notifications(user_id: Optional[int] = None, unread_only: bool = False, limit: int = 50) -> List[Notification]:
        query = Notification.query
        if user_id is not None:
            query = query.filter((Notification.user_id == user_id) | (Notification.user_id.is_(None)))

        if unread_only:
            query = query.filter(Notification.is_read.is_(False))

        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_as_read(notification_id: int, user_id: Optional[int] = None) -> bool:
        notif = db.session.get(Notification, notification_id)
        if notif:
            notif.is_read = True
            db.session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(user_id: Optional[int] = None) -> int:
        query = Notification.query.filter_by(is_read=False)
        if user_id is not None:
            query = query.filter((Notification.user_id == user_id) | (Notification.user_id.is_(None)))
        count = query.update({'is_read': True})
        db.session.commit()
        return count
