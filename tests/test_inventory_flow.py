import pytest
from app.extensions import db
from app.models.product import Product
from app.models.warehouse import Warehouse, Location
from app.services.product_service import ProductService
from app.services.stock_service import StockService, InsufficientStockError
from app.services.warehouse_service import WarehouseService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.models.ledger import StockLedgerEntry

def test_warehouse_and_location_hierarchy(app):
    with app.app_context():
        wh = WarehouseService.create_warehouse(name='East Distribution Center', code='WH-EAST', address='77 Industrial Park')
        assert wh.id is not None
        assert wh.is_active is True

        # Create parent location Rack A
        rack_a = WarehouseService.create_location(
            warehouse_id=wh.id,
            name='Rack A',
            code='WH-EAST/RACK-A',
            location_type='internal'
        )
        assert rack_a.id is not None

        # Create child location Shelf 1 under Rack A
        shelf_1 = WarehouseService.create_location(
            warehouse_id=wh.id,
            name='Shelf 1',
            code='WH-EAST/RACK-A/S1',
            location_type='internal',
            parent_location_id=rack_a.id
        )
        assert shelf_1.parent_location_id == rack_a.id
        assert shelf_1.parent.code == 'WH-EAST/RACK-A'

        # Edit warehouse & location
        WarehouseService.update_warehouse(wh.id, name='East Regional Hub', is_active=False)
        assert wh.name == 'East Regional Hub'
        assert wh.is_active is False

        WarehouseService.update_location(shelf_1.id, name='Shelf 1 (Specialized)', is_active=False)
        assert shelf_1.name == 'Shelf 1 (Specialized)'
        assert shelf_1.is_active is False

def test_product_initial_stock_and_ledger(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']

        p = ProductService.create_product(
            name='Industrial Motor',
            sku='MTR-001',
            uom='Units',
            min_stock_level=5.0,
            initial_stock=40.0,
            initial_location_id=main_stock.id,
            user_id=manager_user_id
        )

        assert p.total_stock == 40.0
        assert p.stock_status == 'in_stock'

        # Verify initial ledger entry
        entry = StockLedgerEntry.query.filter_by(product_id=p.id, movement_type='initial_stock').first()
        assert entry is not None
        assert entry.quantity_change == 40.0
        assert entry.balance_after == 40.0

def test_receipt_flow_and_inactive_location_prevention(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)

        initial_stock = product.total_stock

        # Create incoming receipt for 25 units
        receipt = ReceiptService.create_receipt(
            supplier_name='Supplier X',
            dest_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 25.0}],
            user_id=manager_user_id
        )
        assert receipt.status == 'draft'

        # Validate receipt
        ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)
        assert receipt.status == 'done'

        # Stock should increase by 25
        assert product.total_stock == initial_stock + 25.0

        # Duplicate validation must fail
        with pytest.raises(ValueError, match="already been validated"):
            ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)

        # Inactive destination location must fail
        inactive_loc = WarehouseService.create_location(
            warehouse_id=locs['warehouse'].id,
            name='Decommissioned Aisle',
            code='WH-MAIN/DECOM',
            location_type='internal'
        )
        WarehouseService.update_location(inactive_loc.id, name='Decommissioned Aisle', is_active=False)

        with pytest.raises(ValueError, match="inactive"):
            ReceiptService.create_receipt(
                supplier_name='Supplier Y',
                dest_location_id=inactive_loc.id,
                lines=[{'product_id': product.id, 'demand': 10.0}],
                user_id=manager_user_id
            )

def test_delivery_flow_and_negative_prevention(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)

        initial_stock = product.total_stock  # 100.0

        # Valid delivery of 30 units
        delivery = DeliveryService.create_delivery(
            customer_name='Acme Corp',
            source_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 30.0}],
            user_id=manager_user_id
        )
        DeliveryService.validate_delivery(delivery.id, user_id=manager_user_id)
        assert delivery.status == 'done'
        assert product.total_stock == initial_stock - 30.0  # 70.0

        # Duplicate delivery validation must fail
        with pytest.raises(ValueError, match="already been validated"):
            DeliveryService.validate_delivery(delivery.id, user_id=manager_user_id)

        # Over-demand delivery (e.g. 500 units) must raise InsufficientStockError
        bad_delivery = DeliveryService.create_delivery(
            customer_name='Huge Buyer',
            source_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 500.0}],
            user_id=manager_user_id
        )

        with pytest.raises(InsufficientStockError):
            DeliveryService.validate_delivery(bad_delivery.id, user_id=manager_user_id)

def test_internal_transfer_stock_invariance_and_rules(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)

        # Create second warehouse & location
        wh2 = WarehouseService.create_warehouse(name='South Warehouse', code='WH-SOUTH')
        south_stock = wh2.locations.filter_by(location_type='internal').first()

        initial_total_stock = product.total_stock

        transfer = TransferService.create_transfer(
            source_location_id=main_stock.id,
            dest_location_id=south_stock.id,
            lines=[{'product_id': product.id, 'demand': 20.0}],
            user_id=manager_user_id
        )

        TransferService.validate_transfer(transfer.id, user_id=manager_user_id)
        assert transfer.status == 'done'

        # Total company stock remains unchanged
        assert product.total_stock == initial_total_stock

        # Check location balances
        main_qty = StockService.get_location_stock(product.id, main_stock.id)
        south_qty = StockService.get_location_stock(product.id, south_stock.id)
        assert south_qty == 20.0
        assert main_qty == initial_total_stock - 20.0

        # Duplicate transfer validation must fail
        with pytest.raises(ValueError, match="already been executed"):
            TransferService.validate_transfer(transfer.id, user_id=manager_user_id)

        # Same source & destination must fail
        with pytest.raises(ValueError, match="cannot be the same"):
            TransferService.create_transfer(
                source_location_id=main_stock.id,
                dest_location_id=main_stock.id,
                lines=[{'product_id': product.id, 'demand': 5.0}],
                user_id=manager_user_id
            )
