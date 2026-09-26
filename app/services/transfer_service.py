from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models.operation import StockPicking, StockMove
from app.models.product import Product
from app.models.warehouse import Location
from app.services.stock_service import StockService, InsufficientStockError

class TransferService:
    @staticmethod
    def generate_transfer_number() -> str:
        count = StockPicking.query.filter_by(picking_type='transfer').count() + 1
        return f"INT-{count:05d}"

    @staticmethod
    def create_transfer(
        source_location_id: int,
        dest_location_id: int,
        lines: List[Dict[str, Any]],
        scheduled_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> StockPicking:
        if source_location_id == dest_location_id:
            raise ValueError("Source and destination locations cannot be the same.")

        source_loc = db.session.get(Location, source_location_id)
        if not source_loc or not source_loc.is_active:
            raise ValueError("Source location is invalid or inactive.")

        dest_loc = db.session.get(Location, dest_location_id)
        if not dest_loc or not dest_loc.is_active:
            raise ValueError("Destination location is invalid or inactive.")

        if not lines:
            raise ValueError("Transfer must contain at least one product line.")

        transfer_name = TransferService.generate_transfer_number()

        picking = StockPicking(
            name=transfer_name,
            picking_type='transfer',
            status='draft',
            source_location_id=source_location_id,
            dest_location_id=dest_location_id,
            scheduled_date=scheduled_date or datetime.now(timezone.utc),
            notes=notes.strip() if notes else None,
            created_by_id=user_id
        )
        db.session.add(picking)
        db.session.flush()

        for line in lines:
            product_id = int(line['product_id'])
            demand = float(line.get('demand', 1.0))
            if demand <= 0:
                raise ValueError("Transfer quantity must be greater than zero.")

            prod = db.session.get(Product, product_id)
            if not prod or not prod.is_active:
                raise ValueError(f"Product ID {product_id} is invalid or inactive.")

            move = StockMove(
                picking_id=picking.id,
                product_id=product_id,
                source_location_id=source_location_id,
                dest_location_id=dest_location_id,
                initial_demand=demand,
                quantity_done=0.0,
                status='draft'
            )
            db.session.add(move)

        db.session.commit()
        return picking

    @staticmethod
    def validate_transfer(picking_id: int, user_id: Optional[int] = None, quantities_done: Optional[Dict[int, float]] = None) -> StockPicking:
        """
        Validates internal transfer:
        - Checks available stock at source location.
        - Moves stock atomically: source decreases, dest increases.
        - Preserves total company stock invariant.
        """
        picking = db.session.get(StockPicking, picking_id)
        if not picking or picking.picking_type != 'transfer':
            raise ValueError(f"Internal Transfer ID {picking_id} not found.")

        if picking.status == 'done':
            raise ValueError("This transfer has already been executed.")

        if picking.status == 'canceled':
            raise ValueError("Cannot execute a canceled transfer.")

        if not picking.source_location.is_active or not picking.dest_location.is_active:
            raise ValueError("One of the transfer locations is inactive.")

        # Pre-check stock at source location
        for move in picking.moves:
            if not move.product.is_active:
                raise ValueError(f"Cannot transfer inactive product '{move.product.name}'.")

            qty_to_move = move.initial_demand
            if quantities_done and move.id in quantities_done:
                qty_to_move = float(quantities_done[move.id])

            if qty_to_move <= 0:
                raise ValueError("Transferred quantity must be greater than zero.")

            available_stock = StockService.get_location_stock(move.product_id, move.source_location_id)
            if available_stock < qty_to_move:
                raise InsufficientStockError(
                    f"Insufficient stock for product '{move.product.name}' (SKU: {move.product.sku}) at '{move.source_location.full_name}'. "
                    f"Required: {qty_to_move}, Available: {available_stock}"
                )

        # Execute moves
        for move in picking.moves:
            qty_to_move = move.initial_demand
            if quantities_done and move.id in quantities_done:
                qty_to_move = float(quantities_done[move.id])

            move.quantity_done = qty_to_move
            StockService.execute_move(move, user_id=user_id, reference_doc=picking.name)

        picking.status = 'done'
        picking.date_done = datetime.now(timezone.utc)
        picking.validated_by_id = user_id

        db.session.commit()
        return picking
