import pytest
from app.extensions import db
from app.models.product import Product
from app.models.operation import StockPicking
from app.models.ledger import StockLedgerEntry
from app.services.warehouse_service import WarehouseService
from app.services.product_service import ProductService
from app.services.receipt_service import ReceiptService

def test_receipt_create_and_validation(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)
        initial_stock = product.total_stock  # 100.0

        # 1. Create Receipt
        receipt = ReceiptService.create_receipt(
            supplier_name='Global Metals Inc',
            dest_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 50.0}],
            notes='Shipment batch #A1',
            user_id=manager_user_id
        )
        assert receipt.id is not None
        assert receipt.picking_type == 'receipt'
        assert receipt.status == 'draft'
        assert len(receipt.moves) == 1

        # 2. Validate Receipt
        ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)
        assert receipt.status == 'done'
        assert receipt.date_done is not None
        assert receipt.validated_by_id == manager_user_id

        # 3. Verify Stock Increase
        assert product.total_stock == initial_stock + 50.0

        # 4. Verify Ledger Creation
        ledger_entry = StockLedgerEntry.query.filter_by(
            reference_document=receipt.name,
            movement_type='receipt',
            product_id=product.id,
            location_id=main_stock.id
        ).first()
        assert ledger_entry is not None
        assert ledger_entry.quantity_change == 50.0
        assert ledger_entry.balance_after == initial_stock + 50.0

        # 5. Prevent Duplicate Validation
        with pytest.raises(ValueError, match="already been validated"):
            ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)


def test_receipt_custom_quantity_done(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)
        initial_stock = product.total_stock

        receipt = ReceiptService.create_receipt(
            supplier_name='Precision Supplies',
            dest_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 30.0}],
            user_id=manager_user_id
        )
        move_id = receipt.moves[0].id

        # Receive partial or extra (e.g., 28 units actually delivered)
        ReceiptService.validate_receipt(
            receipt.id,
            user_id=manager_user_id,
            quantities_done={move_id: 28.0}
        )
        assert receipt.status == 'done'
        assert product.total_stock == initial_stock + 28.0


def test_receipt_invalid_cases(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']

        # Empty lines
        with pytest.raises(ValueError, match="at least one product line"):
            ReceiptService.create_receipt(
                supplier_name='Supplier',
                dest_location_id=main_stock.id,
                lines=[],
                user_id=manager_user_id
            )

        # Inactive destination location
        inactive_loc = WarehouseService.create_location(
            warehouse_id=locs['warehouse'].id,
            name='Closed Bay',
            code='WH-MAIN/CLOSED',
            location_type='internal'
        )
        WarehouseService.update_location(inactive_loc.id, name='Closed Bay', is_active=False)

        with pytest.raises(ValueError, match="inactive"):
            ReceiptService.create_receipt(
                supplier_name='Supplier',
                dest_location_id=inactive_loc.id,
                lines=[{'product_id': sample_product_id, 'demand': 10.0}],
                user_id=manager_user_id
            )
