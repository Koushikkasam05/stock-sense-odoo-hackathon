from datetime import datetime, timezone
from typing import Optional, Tuple
from app.extensions import db
from app.models.product import Product, StockQuant
from app.models.warehouse import Location
from app.models.ledger import StockLedgerEntry
from app.models.operation import StockMove

class StockServiceError(Exception):
    """Base exception for inventory service operations."""
    pass

class InsufficientStockError(StockServiceError):
    """Raised when an operation would cause invalid negative stock."""
    pass


class StockService:
    @staticmethod
    def get_or_create_quant(product_id: int, location_id: int) -> StockQuant:
        """Fetch or initialize the StockQuant record for a product at a specific location."""
        quant = StockQuant.query.filter_by(product_id=product_id, location_id=location_id).first()
        if not quant:
            quant = StockQuant(product_id=product_id, location_id=location_id, quantity=0.0, reserved_quantity=0.0)
            db.session.add(quant)
            db.session.flush()
        return quant

    @staticmethod
    def get_location_stock(product_id: int, location_id: int) -> float:
        """Returns the current on-hand quantity for a product at a specific location."""
        quant = StockQuant.query.filter_by(product_id=product_id, location_id=location_id).first()
        return float(quant.quantity) if quant else 0.0

    @staticmethod
    def get_product_total_stock(product_id: int) -> float:
        """Returns the total stock across all active internal locations."""
        total = db.session.query(db.func.coalesce(db.func.sum(StockQuant.quantity), 0.0))\
            .join(Location, StockQuant.location_id == Location.id)\
            .filter(
                StockQuant.product_id == product_id,
                Location.location_type == 'internal',
                Location.is_active.is_(True)
            ).scalar()
        return float(total or 0.0)

    @staticmethod
    def record_stock_movement(
        product_id: int,
        location_id: int,
        qty_delta: float,
        movement_type: str,
        reference_document: str,
        picking_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        allow_negative: bool = False
    ) -> Tuple[StockQuant, StockLedgerEntry]:
        """
        Transaction-safe stock modification.
        Updates StockQuant and writes an immutable StockLedgerEntry atomically.
        Enforces negative stock prevention on internal locations unless overridden.
        """
        product = db.session.get(Product, product_id)
        if not product:
            raise StockServiceError(f"Product ID {product_id} not found.")

        location = db.session.get(Location, location_id)
        if not location:
            raise StockServiceError(f"Location ID {location_id} not found.")

        # Virtual locations (vendor, customer, loss) are allowed negative balances
        is_internal = (location.location_type == 'internal')
        
        quant = StockService.get_or_create_quant(product_id, location_id)
        new_quantity = round(quant.quantity + qty_delta, 4)

        if is_internal and not allow_negative and new_quantity < 0:
            raise InsufficientStockError(
                f"Insufficient stock for product '{product.name}' (SKU: {product.sku}) at location '{location.full_name}'. "
                f"Available: {quant.quantity}, Requested: {abs(qty_delta)}"
            )

        quant.quantity = new_quantity
        quant.updated_at = datetime.now(timezone.utc)

        # Write immutable audit entry
        ledger_entry = StockLedgerEntry(
            timestamp=datetime.now(timezone.utc),
            product_id=product_id,
            location_id=location_id,
            movement_type=movement_type,
            quantity_change=qty_delta,
            balance_after=new_quantity,
            reference_document=reference_document,
            picking_id=picking_id,
            user_id=user_id,
            notes=notes
        )
        db.session.add(ledger_entry)
        db.session.flush()

        return quant, ledger_entry

    @staticmethod
    def execute_move(move: StockMove, user_id: Optional[int] = None, reference_doc: Optional[str] = None) -> None:
        """
        Executes a paired move from source location to destination location.
        For internal transfers:
          - Decrements source location (movement_type='transfer_out')
          - Increments destination location (movement_type='transfer_in')
        Total company stock is strictly preserved.
        """
        qty = float(move.quantity_done or move.initial_demand)
        if qty <= 0:
            return

        doc = reference_doc or (move.picking.name if move.picking else "STOCK-MOVE")
        
        # Determine source and dest movement types based on location types
        src_loc = move.source_location
        dest_loc = move.dest_location

        if src_loc.location_type == 'vendor':
            src_type = 'receipt_source'
            dest_type = 'receipt'
        elif dest_loc.location_type == 'customer':
            src_type = 'delivery'
            dest_type = 'delivery_dest'
        elif dest_loc.location_type == 'loss':
            src_type = 'adjustment_loss'
            dest_type = 'loss_sink'
        elif src_loc.location_type == 'loss':
            src_type = 'loss_source'
            dest_type = 'adjustment_gain'
        else:
            src_type = 'transfer_out'
            dest_type = 'transfer_in'

        # Decrement source
        StockService.record_stock_movement(
            product_id=move.product_id,
            location_id=move.source_location_id,
            qty_delta=-qty,
            movement_type=src_type,
            reference_document=doc,
            picking_id=move.picking_id,
            user_id=user_id,
            notes=f"Move to {dest_loc.full_name}",
            allow_negative=(src_loc.location_type != 'internal')
        )

        # Increment destination
        StockService.record_stock_movement(
            product_id=move.product_id,
            location_id=move.dest_location_id,
            qty_delta=qty,
            movement_type=dest_type,
            reference_document=doc,
            picking_id=move.picking_id,
            user_id=user_id,
            notes=f"Move from {src_loc.full_name}",
            allow_negative=(dest_loc.location_type != 'internal')
        )

        move.status = 'done'
        move.quantity_done = qty
