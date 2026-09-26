from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy import func
from app.extensions import db
from app.models.ledger import StockLedgerEntry
from app.models.product import Product

class MovementAnalysisService:
    """
    Analyzes historical inventory velocity over a configurable period (default: 30 days).
    Classifies products into: Fast Moving, Normal Moving, Slow Moving, No Movement.
    """

    @staticmethod
    def get_movement_status(product_id: int, days: int = 30) -> Dict[str, Any]:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Count transactions & total outgoing units
        entries = StockLedgerEntry.query.filter(
            StockLedgerEntry.product_id == product_id,
            StockLedgerEntry.timestamp >= cutoff_date
        ).all()

        total_tx_count = len(entries)
        outgoing_qty = sum(abs(e.quantity_change) for e in entries if e.quantity_change < 0)
        incoming_qty = sum(e.quantity_change for e in entries if e.quantity_change > 0)

        if total_tx_count == 0 or outgoing_qty == 0:
            status = 'No Movement'
            badge_class = 'badge bg-secondary'
        elif outgoing_qty >= 50 or total_tx_count >= 10:
            status = 'Fast Moving'
            badge_class = 'badge bg-success'
        elif outgoing_qty >= 15 or total_tx_count >= 4:
            status = 'Normal Moving'
            badge_class = 'badge bg-info text-dark'
        else:
            status = 'Slow Moving'
            badge_class = 'badge bg-warning text-dark'

        return {
            'status': status,
            'badge_class': badge_class,
            'tx_count': total_tx_count,
            'outgoing_qty': outgoing_qty,
            'incoming_qty': incoming_qty,
            'period_days': days
        }
