from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint
from app.extensions import db

class ProductCategory(db.Model):
    __tablename__ = 'product_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    products = db.relationship('Product', backref='category', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<ProductCategory {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    sku = db.Column(db.String(50), nullable=False, unique=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('product_categories.id', ondelete='SET NULL'), nullable=True, index=True)
    uom = db.Column(db.String(20), nullable=False, default='Units')  # e.g., Units, Kg, Box, Liters, Meters
    min_stock_level = db.Column(db.Float, default=10.0, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    stock_quants = db.relationship('StockQuant', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    stock_moves = db.relationship('StockMove', backref='product', lazy='dynamic')
    ledger_entries = db.relationship('StockLedgerEntry', backref='product', lazy='dynamic')

    @property
    def total_stock(self) -> float:
        """Sum of on-hand quantities across all internal locations."""
        from app.models.warehouse import Location
        total = db.session.query(db.func.coalesce(db.func.sum(StockQuant.quantity), 0.0))\
            .join(Location, StockQuant.location_id == Location.id)\
            .filter(StockQuant.product_id == self.id, Location.location_type == 'internal')\
            .scalar()
        return float(total or 0.0)

    @property
    def is_low_stock(self) -> bool:
        stock = self.total_stock
        return 0 < stock <= self.min_stock_level

    @property
    def is_out_of_stock(self) -> bool:
        return self.total_stock <= 0

    @property
    def stock_status(self) -> str:
        stock = self.total_stock
        if stock <= 0:
            return 'out_of_stock'
        if stock <= self.min_stock_level:
            return 'low_stock'
        return 'in_stock'

    def __repr__(self) -> str:
        return f'<Product {self.sku} - {self.name}>'


class StockQuant(db.Model):
    """Represents real-time stock balance at a specific location."""
    __tablename__ = 'stock_quants'
    __table_args__ = (
        UniqueConstraint('product_id', 'location_id', name='uq_product_location_quant'),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True)
    quantity = db.Column(db.Float, default=0.0, nullable=False)
    reserved_quantity = db.Column(db.Float, default=0.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def available_quantity(self) -> float:
        return max(0.0, self.quantity - self.reserved_quantity)

    def __repr__(self) -> str:
        return f'<StockQuant Product:{self.product_id} Loc:{self.location_id} Qty:{self.quantity}>'
