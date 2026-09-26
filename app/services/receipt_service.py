from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models.operation import StockPicking, StockMove
from app.models.product import Product
from app.models.warehouse import Location
from app.services.stock_service import StockService, StockServiceError
from app.services.warehouse_service import WarehouseService

class ReceiptService:
    @staticmethod
    def generate_receipt_number() -> str:
        count = StockPicking.query.filter_by(picking_type='receipt').count() + 1
        return f"REC-{count:05d}"

    @staticmethod
    def create_receipt(
        supplier_name: str,
        dest_location_id: int,
        lines: List[Dict[str, Any]],
        scheduled_date: Optional[datetime] = None,
        notes: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> StockPicking:
        """
        Creates an incoming stock receipt.
        Source location is the virtual Vendor location.
        """
        if not lines:
            raise ValueError("Receipt must contain at least one product line.")

        dest_loc = db.session.get(Location, dest_location_id)
        if not dest_loc or not dest_loc.is_active:
            raise ValueError("Destination location is invalid or inactive.")

        vendor_loc = WarehouseService.get_vendor_location()
        receipt_name = ReceiptService.generate_receipt_number()

        picking = StockPicking(
            name=receipt_name,
            picking_type='receipt',
            status='draft',
            partner_name=supplier_name.strip() if supplier_name else "Supplier",
            source_location_id=vendor_loc.id,
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
                raise ValueError(f"Received quantity must be greater than zero.")

            prod = db.session.get(Product, product_id)
            if not prod or not prod.is_active:
                raise ValueError(f"Product ID {product_id} is invalid or inactive.")

            move = StockMove(
                picking_id=picking.id,
                product_id=product_id,
                source_location_id=vendor_loc.id,
                dest_location_id=dest_location_id,
                initial_demand=demand,
                quantity_done=0.0,
                status='draft'
            )
            db.session.add(move)

        db.session.commit()
        return picking

    @staticmethod
    def validate_receipt(picking_id: int, user_id: Optional[int] = None, quantities_done: Optional[Dict[int, float]] = None) -> StockPicking:
        """
        Validates an incoming receipt:
        - Transfers stock from Vendor location into the destination internal location.
        - Increases physical stock balance.
        - Creates audit entries in the stock ledger.
        """
        picking = db.session.get(StockPicking, picking_id)
        if not picking or picking.picking_type != 'receipt':
            raise ValueError(f"Receipt ID {picking_id} not found.")

        if picking.status == 'done':
            raise ValueError("This receipt has already been validated and processed.")

        if picking.status == 'canceled':
            raise ValueError("Cannot validate a canceled receipt.")

        if not picking.dest_location.is_active:
            raise ValueError(f"Destination location '{picking.dest_location.full_name}' is inactive and cannot receive stock.")

        for move in picking.moves:
            qty_done = move.initial_demand
            if quantities_done and move.id in quantities_done:
                qty_done = float(quantities_done[move.id])

            if qty_done <= 0:
                raise ValueError(f"Quantity to validate must be greater than zero.")

            move.quantity_done = qty_done
            StockService.execute_move(move, user_id=user_id, reference_doc=picking.name)

        picking.status = 'done'
        picking.date_done = datetime.now(timezone.utc)
        picking.validated_by_id = user_id

        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log_event(
            action='STOCK_RECEIVED',
            resource_type='stock_picking',
            resource_id=str(picking.id),
            details=f"Receipt {picking.name} validated at {picking.dest_location.full_name} from {picking.partner_name or 'Supplier'}",
            user_id=user_id
        )
        return picking
