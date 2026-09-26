from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.products import products_bp
from app.routes.warehouses import warehouses_bp
from app.routes.receipts import receipts_bp
from app.routes.deliveries import deliveries_bp
from app.routes.transfers import transfers_bp
from app.routes.adjustments import adjustments_bp
from app.routes.ledger import ledger_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'products_bp',
    'warehouses_bp',
    'receipts_bp',
    'deliveries_bp',
    'transfers_bp',
    'adjustments_bp',
    'ledger_bp'
]
