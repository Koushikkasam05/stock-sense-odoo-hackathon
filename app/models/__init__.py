from app.models.user import User, OTPToken
from app.models.warehouse import Warehouse, Location
from app.models.product import ProductCategory, Product, StockQuant
from app.models.operation import StockPicking, StockMove
from app.models.ledger import StockLedgerEntry
from app.models.notification import Notification
from app.models.audit import AuditLog

# Schema Model Aliases for flexible naming conventions
Category = ProductCategory
StockBalance = StockQuant
StockLedger = StockLedgerEntry

__all__ = [
    'User',
    'OTPToken',
    'Notification',
    'AuditLog',
    'Warehouse',
    'Location',
    'ProductCategory',
    'Category',
    'Product',
    'StockQuant',
    'StockBalance',
    'StockPicking',
    'StockMove',
    'StockLedgerEntry',
    'StockLedger'
]
