from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from app.extensions import db
from app.models.ledger import StockLedgerEntry
from app.models.operation import StockMove, StockPicking

class DemandAnalysisService:
    """
    Evaluates product consumption and order trends based on verified outgoing moves and deliveries.
    Classifies products into: High Demand, Medium Demand, Low Demand, or Insufficient data.
    """

    @staticmethod
    def get_demand_status(product_id: int, days: int = 30) -> Dict[str, Any]:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Retrieve outgoing ledger movements (deliveries / consumption)
        outgoing_entries = StockLedgerEntry.query.filter(
            StockLedgerEntry.product_id == product_id,
            StockLedgerEntry.quantity_change < 0,
            StockLedgerEntry.timestamp >= cutoff_date
        ).all()

        total_entries_count = StockLedgerEntry.query.filter(
            StockLedgerEntry.product_id == product_id
        ).count()

        # If product has virtually no historical transactions, report Insufficient data
        if total_entries_count < 2:
            return {
                'status': 'Insufficient data',
                'badge_class': 'badge bg-light text-dark border',
                'demand_score': 0.0,
                'outgoing_orders': len(outgoing_entries)
            }

        total_consumed = sum(abs(e.quantity_change) for e in outgoing_entries)
        order_frequency = len(outgoing_entries)

        if total_consumed >= 40 or order_frequency >= 6:
            status = 'High Demand'
            badge_class = 'badge bg-danger'
        elif total_consumed >= 10 or order_frequency >= 2:
            status = 'Medium Demand'
            badge_class = 'badge bg-primary'
        else:
            status = 'Low Demand'
            badge_class = 'badge bg-secondary'

        return {
            'status': status,
            'badge_class': badge_class,
            'demand_score': float(total_consumed),
            'outgoing_orders': order_frequency
        }
