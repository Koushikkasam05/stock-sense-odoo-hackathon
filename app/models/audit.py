from datetime import datetime, timezone
from app.extensions import db

class AuditLog(db.Model):
    """
    Comprehensive Security and Business Audit Log.
    Records administrative actions, master data mutations, stock adjustments, and authentication events.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    username = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(32), nullable=True)
    
    action = db.Column(db.String(50), nullable=False, index=True)
    # Examples: 'USER_LOGIN', 'USER_LOGOUT', 'PRODUCT_CREATED', 'PRODUCT_UPDATED', 'STOCK_RECEIVED', 'STOCK_TRANSFERRED', 'STOCK_ADJUSTED'
    
    resource_type = db.Column(db.String(50), nullable=False, index=True) # 'product', 'warehouse', 'stock_picking', 'user', 'auth'
    resource_id = db.Column(db.String(50), nullable=True)
    
    details = db.Column(db.Text, nullable=True) # JSON or formatted string of changes (old vs new)
    ip_address = db.Column(db.String(50), nullable=True)

    def __repr__(self) -> str:
        return f'<AuditLog id={self.id} action={self.action} user={self.username} time={self.timestamp}>'
