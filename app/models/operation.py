from datetime import datetime, timezone
from app.extensions import db

class StockPicking(db.Model):
    """
    Unified Inventory Operation model covering:
    - Receipts (Vendor -> Internal Location)
    - Deliveries (Internal Location -> Customer)
    - Internal Transfers (Internal Loc A -> Internal Loc B)
    - Inventory Adjustments (Internal Loc <-> Virtual Loss/Inventory)
    """
    __tablename__ = 'stock_pickings'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True, index=True)
    # picking_type: 'receipt', 'delivery', 'transfer', 'adjustment'
    picking_type = db.Column(db.String(20), nullable=False, index=True)
    # status: 'draft', 'waiting', 'ready', 'done', 'canceled'
    status = db.Column(db.String(20), default='draft', nullable=False, index=True)
    
    # Partner info (Supplier for Receipts, Customer for Deliveries)
    partner_name = db.Column(db.String(150), nullable=True)

    # Locations
    source_location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False, index=True)
    dest_location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False, index=True)

    # Metadata & Tracking
    scheduled_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    date_done = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    validated_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    source_location = db.relationship('Location', foreign_keys=[source_location_id], backref='outgoing_pickings')
    dest_location = db.relationship('Location', foreign_keys=[dest_location_id], backref='incoming_pickings')
    moves = db.relationship('StockMove', backref='picking', lazy='selectin', cascade='all, delete-orphan')
    ledger_entries = db.relationship('StockLedgerEntry', backref='picking', lazy='dynamic')

    @property
    def badge_class(self) -> str:
        mapping = {
            'draft': 'bg-secondary',
            'waiting': 'bg-warning text-dark',
            'ready': 'bg-info text-dark',
            'done': 'bg-success',
            'canceled': 'bg-danger'
        }
        return mapping.get(self.status, 'bg-secondary')

    @property
    def type_display(self) -> str:
        mapping = {
            'receipt': 'Receipt (Incoming)',
            'delivery': 'Delivery (Outgoing)',
            'transfer': 'Internal Transfer',
            'adjustment': 'Inventory Adjustment'
        }
        return mapping.get(self.picking_type, self.picking_type.capitalize())

    def __repr__(self) -> str:
        return f'<StockPicking {self.name} ({self.picking_type}) [{self.status}]>'


class StockMove(db.Model):
    """Line item move representing an item and quantity within a picking operation."""
    __tablename__ = 'stock_moves'

    id = db.Column(db.Integer, primary_key=True)
    picking_id = db.Column(db.Integer, db.ForeignKey('stock_pickings.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    
    # Locations
    source_location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False)
    dest_location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False)

    initial_demand = db.Column(db.Float, default=1.0, nullable=False)
    quantity_done = db.Column(db.Float, default=0.0, nullable=False)
    
    # Status mirrored from picking or per-line
    status = db.Column(db.String(20), default='draft', nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    source_location = db.relationship('Location', foreign_keys=[source_location_id])
    dest_location = db.relationship('Location', foreign_keys=[dest_location_id])

    def __repr__(self) -> str:
        return f'<StockMove Picking:{self.picking_id} Product:{self.product_id} Demand:{self.initial_demand} Done:{self.quantity_done}>'
