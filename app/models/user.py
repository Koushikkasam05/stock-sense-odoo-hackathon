from datetime import datetime, timezone
import bcrypt
from flask_login import UserMixin
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mobile_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='warehouse_staff')  # 'inventory_manager' or 'warehouse_staff'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    otp_tokens = db.relationship('OTPToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    created_pickings = db.relationship('StockPicking', foreign_keys='StockPicking.created_by_id', backref='creator', lazy='dynamic')
    validated_pickings = db.relationship('StockPicking', foreign_keys='StockPicking.validated_by_id', backref='validator', lazy='dynamic')
    ledger_entries = db.relationship('StockLedgerEntry', backref='user', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password: str) -> None:
        """Hash and set user password using bcrypt."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Verify user password."""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @property
    def is_manager(self) -> bool:
        return self.role == 'inventory_manager'

    @property
    def role_display(self) -> str:
        return 'Inventory Manager' if self.role == 'inventory_manager' else 'Warehouse Staff'

    def __repr__(self) -> str:
        return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class OTPToken(db.Model):
    __tablename__ = 'otp_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    otp_code = db.Column(db.String(6), nullable=False, index=True)
    purpose = db.Column(db.String(32), default='password_reset', nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def is_valid(self) -> bool:
        """Check if OTP is not used and not expired."""
        now = datetime.now(timezone.utc)
        # Handle naive vs aware datetime if needed
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return not self.is_used and now <= expires

    def __repr__(self) -> str:
        return f'<OTPToken user_id={self.user_id} purpose={self.purpose} used={self.is_used}>'
