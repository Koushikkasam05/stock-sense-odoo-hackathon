from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.services.notification_service import NotificationService

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def index():
    notifications = NotificationService.get_user_notifications(user_id=current_user.id, limit=100)
    return render_template('notifications/index.html', notifications=notifications)

@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id: int):
    NotificationService.mark_as_read(notification_id, user_id=current_user.id)
    return redirect(url_for('notifications.index'))

@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    NotificationService.mark_all_as_read(user_id=current_user.id)
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('notifications.index'))
