from datetime import datetime, timezone
from app.extensions import db

class StockLedgerEntry(db.Model):
    """
    Immutable Audit Log tracking every physical inventory movement.
    Provides complete traceability for receipts, deliveries, internal transfers, and adjustments.
    """
    __tablename__ = 'stock_ledger_entries'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='RESTRICT'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='RESTRICT'), nullable=False, index=True)
    
    # movement_type: 'receipt', 'delivery', 'transfer_in', 'transfer_out', 'adjustment_gain', 'adjustment_loss', 'initial_stock'
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    
    # Signed quantity change (+ for stock added, - for stock deducted)
    quantity_change = db.Column(db.Float, nullable=False)
    
    # Balance at this location immediately after this transaction
    balance_after = db.Column(db.Float, nullable=False)
    
    reference_document = db.Column(db.String(100), nullable=False, index=True)
    picking_id = db.Column(db.Integer, db.ForeignKey('stock_pickings.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    notes = db.Column(db.String(255), nullable=True)

    @property
    def badge_class(self) -> str:
        if self.quantity_change > 0:
            return 'bg-success text-white'
        elif self.quantity_change < 0:
            return 'bg-danger text-white'
        return 'bg-secondary text-white'

    def __repr__(self) -> str:
        return f'<StockLedgerEntry {self.reference_document} Prod:{self.product_id} Loc:{self.location_id} Change:{self.quantity_change}>'
