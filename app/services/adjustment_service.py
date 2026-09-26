from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from app.extensions import db
from app.models.operation import StockPicking, StockMove
from app.models.product import Product, StockQuant
from app.models.warehouse import Location
from app.services.stock_service import StockService
from app.services.warehouse_service import WarehouseService

class AdjustmentService:
    @staticmethod
    def generate_adjustment_number() -> str:
        count = StockPicking.query.filter_by(picking_type='adjustment').count() + 1
        return f"ADJ-{count:05d}"

    @staticmethod
    def get_inventory_count_lines(location_id: int) -> List[Dict[str, Any]]:
        """Returns all products with their current system stock at a given location."""
        products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
        lines = []
        for p in products:
            quant = StockQuant.query.filter_by(product_id=p.id, location_id=location_id).first()
            sys_qty = float(quant.quantity) if quant else 0.0
            lines.append({
                'product_id': p.id,
                'product_name': p.name,
                'sku': p.sku,
                'uom': p.uom,
                'system_quantity': sys_qty
            })
        return lines

    @staticmethod
    def apply_adjustment(
        location_id: int,
        product_id: int,
        counted_quantity: float,
        reason: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> StockPicking:
        """
        Calculates difference between physical count and system quantity.
        If difference != 0, adjusts stock to counted quantity and logs audit record in ledger.
        """
        if counted_quantity < 0:
            raise ValueError("Physical counted quantity cannot be negative.")

        location = db.session.get(Location, location_id)
        if not location or not location.is_active:
            raise ValueError(f"Location ID {location_id} is invalid or inactive.")

        product = db.session.get(Product, product_id)
        if not product or not product.is_active:
            raise ValueError(f"Product ID {product_id} is invalid or inactive.")

        quant = StockService.get_or_create_quant(product_id, location_id)
        system_quantity = quant.quantity
        diff = round(counted_quantity - system_quantity, 4)

        loss_loc = WarehouseService.get_loss_location()
        adj_name = AdjustmentService.generate_adjustment_number()

        # Create audit picking record for this adjustment
        picking = StockPicking(
            name=adj_name,
            picking_type='adjustment',
            status='done',
            source_location_id=loss_loc.id if diff >= 0 else location_id,
            dest_location_id=location_id if diff >= 0 else loss_loc.id,
            scheduled_date=datetime.now(timezone.utc),
            date_done=datetime.now(timezone.utc),
            notes=f"Physical Count: {counted_quantity} (Sys: {system_quantity}, Diff: {diff:+}). Reason: {reason or 'Regular audit'}",
            created_by_id=user_id,
            validated_by_id=user_id
        )
        db.session.add(picking)
        db.session.flush()

        move = StockMove(
            picking_id=picking.id,
            product_id=product_id,
            source_location_id=picking.source_location_id,
            dest_location_id=picking.dest_location_id,
            initial_demand=abs(diff),
            quantity_done=abs(diff),
            status='done'
        )
        db.session.add(move)

        if diff != 0:
            movement_type = 'adjustment_gain' if diff > 0 else 'adjustment_loss'
            # Directly record stock movement with StockService
            StockService.record_stock_movement(
                product_id=product_id,
                location_id=location_id,
                qty_delta=diff,
                movement_type=movement_type,
                reference_document=adj_name,
                picking_id=picking.id,
                user_id=user_id,
                notes=f"Physical count adjustment: {system_quantity} -> {counted_quantity} ({reason or 'Audit'})",
                allow_negative=False
            )

        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log_event(
            action='STOCK_ADJUSTED',
            resource_type='stock_picking',
            resource_id=str(picking.id),
            details=f"Adjustment {picking.name}: {product.name} at {location.full_name} from {system_quantity} to {counted_quantity} (Diff: {diff:+}). Reason: {reason or 'Audit'}",
            user_id=user_id
        )
        return picking
