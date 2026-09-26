from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models.operation import StockPicking, StockMove
from app.models.product import Product
from app.models.warehouse import Location
from app.services.stock_service import StockService, InsufficientStockError
from app.services.warehouse_service import WarehouseService

class DeliveryService:
    @staticmethod
    def generate_delivery_number() -> str:
        count = StockPicking.query.filter_by(picking_type='delivery').count() + 1
        return f"DEL-{count:05d}"

    @staticmethod
    def create_delivery(
        customer_name: str,
        source_location_id: int,
        lines: List[Dict[str, Any]],
        scheduled_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> StockPicking:
        """
        Creates an outgoing delivery order.
        Destination location is the virtual Customer location.
        """
        if not lines:
            raise ValueError("Delivery order must contain at least one product line.")

        source_loc = db.session.get(Location, source_location_id)
        if not source_loc or not source_loc.is_active:
            raise ValueError("Source location is invalid or inactive.")

        customer_loc = WarehouseService.get_customer_location()
        delivery_name = DeliveryService.generate_delivery_number()

        picking = StockPicking(
            name=delivery_name,
            picking_type='delivery',
            status='draft',
            partner_name=customer_name.strip() if customer_name else "Customer",
            source_location_id=source_location_id,
            dest_location_id=customer_loc.id,
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
                raise ValueError("Delivery quantity demand must be greater than zero.")

            prod = db.session.get(Product, product_id)
            if not prod or not prod.is_active:
                raise ValueError(f"Product ID {product_id} is invalid or inactive.")

            move = StockMove(
                picking_id=picking.id,
                product_id=product_id,
                source_location_id=source_location_id,
                dest_location_id=customer_loc.id,
                initial_demand=demand,
                quantity_done=0.0,
                status='draft'
            )
            db.session.add(move)

        db.session.commit()
        return picking

    @staticmethod
    def advance_status(picking_id: int, target_status: str, user_id: Optional[int] = None) -> StockPicking:
        """
        Supports Pick / Pack workflow:
        draft -> waiting -> ready
        """
        picking = db.session.get(StockPicking, picking_id)
        if not picking or picking.picking_type != 'delivery':
            raise ValueError(f"Delivery order ID {picking_id} not found.")

        if target_status not in ['draft', 'waiting', 'ready', 'canceled']:
            raise ValueError(f"Invalid target status '{target_status}'.")

        if picking.status == 'done':
            raise ValueError("Cannot modify a completed delivery order.")

        picking.status = target_status
        for move in picking.moves:
            move.status = target_status

        db.session.commit()
        return picking

    @staticmethod
    def validate_delivery(picking_id: int, user_id: Optional[int] = None, quantities_done: Optional[Dict[int, float]] = None) -> StockPicking:
        """
        Validates delivery:
        - Verifies stock is available in source location.
        - Decrements stock from source location.
        - Records immutable stock ledger entries.
        """
        picking = db.session.get(StockPicking, picking_id)
        if not picking or picking.picking_type != 'delivery':
            raise ValueError(f"Delivery order ID {picking_id} not found.")

        if picking.status == 'done':
            raise ValueError("This delivery order has already been validated and shipped.")

        if picking.status == 'canceled':
            raise ValueError("Cannot validate a canceled delivery order.")

        if not picking.source_location.is_active:
            raise ValueError(f"Source location '{picking.source_location.full_name}' is inactive.")

        # Check stock availability and active state for all lines before executing
        for move in picking.moves:
            if not move.product.is_active:
                raise ValueError(f"Cannot dispatch inactive product '{move.product.name}'.")

            qty_to_deliver = move.initial_demand
            if quantities_done and move.id in quantities_done:
                qty_to_deliver = float(quantities_done[move.id])

            if qty_to_deliver <= 0:
                raise ValueError("Delivered quantity must be greater than zero.")

            available_stock = StockService.get_location_stock(move.product_id, move.source_location_id)
            if available_stock < qty_to_deliver:
                raise InsufficientStockError(
                    f"Insufficient stock for product '{move.product.name}' (SKU: {move.product.sku}) at '{move.source_location.full_name}'. "
                    f"Required: {qty_to_deliver}, Available: {available_stock}"
                )

        # Execute all moves
        for move in picking.moves:
            qty_to_deliver = move.initial_demand
            if quantities_done and move.id in quantities_done:
                qty_to_deliver = float(quantities_done[move.id])

            move.quantity_done = qty_to_deliver
            StockService.execute_move(move, user_id=user_id, reference_doc=picking.name)

        picking.status = 'done'
        picking.date_done = datetime.now(timezone.utc)
        picking.validated_by_id = user_id

        db.session.commit()
        return picking
