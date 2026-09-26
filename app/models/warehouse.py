from datetime import datetime, timezone
from app.extensions import db

class Warehouse(db.Model):
    __tablename__ = 'warehouses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True, index=True)
    address = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    locations = db.relationship('Location', backref='warehouse', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f'<Warehouse {self.code} - {self.name}>'


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id', ondelete='CASCADE'), nullable=True, index=True)
    parent_location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='SET NULL'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(30), nullable=False, unique=True, index=True)
    # location_type: 'internal' (stock location), 'vendor' (partner receipt source), 'customer' (delivery dest), 'loss' (scrap/adjustment)
    location_type = db.Column(db.String(30), default='internal', nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    children = db.relationship('Location', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    stock_quants = db.relationship('StockQuant', backref='location', lazy='dynamic')
    ledger_entries = db.relationship('StockLedgerEntry', backref='location', lazy='dynamic')

    @property
    def full_name(self) -> str:
        if self.warehouse:
            return f"{self.warehouse.code}/{self.name}"
        return self.name

    def __repr__(self) -> str:
        return f'<Location {self.code} ({self.location_type})>'
