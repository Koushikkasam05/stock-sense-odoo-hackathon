import pytest
from app.extensions import db
from app.models.product import Product
from app.models.operation import StockPicking
from app.models.ledger import StockLedgerEntry
from app.services.warehouse_service import WarehouseService
from app.services.product_service import ProductService
from app.services.delivery_service import DeliveryService
from app.services.stock_service import InsufficientStockError

def test_delivery_create_and_validation(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)
        initial_stock = product.total_stock  # 100.0

        # 1. Create Delivery Order
        delivery = DeliveryService.create_delivery(
            customer_name='Acme Aerospace',
            source_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 25.0}],
            notes='Urgent dispatch',
            user_id=manager_user_id
        )
        assert delivery.id is not None
        assert delivery.picking_type == 'delivery'
        assert delivery.status == 'draft'

        # 2. Advance Status (Workflow)
        DeliveryService.advance_status(delivery.id, 'waiting', user_id=manager_user_id)
        assert delivery.status == 'waiting'

        DeliveryService.advance_status(delivery.id, 'ready', user_id=manager_user_id)
        assert delivery.status == 'ready'

        # 3. Validate Delivery
        DeliveryService.validate_delivery(delivery.id, user_id=manager_user_id)
        assert delivery.status == 'done'
        assert delivery.date_done is not None

        # 4. Verify Stock Decrease
        assert product.total_stock == initial_stock - 25.0  # 75.0

        # 5. Verify Ledger Entry
        ledger_entry = StockLedgerEntry.query.filter_by(
            reference_document=delivery.name,
            movement_type='delivery',
            product_id=product.id,
            location_id=main_stock.id
        ).first()
        assert ledger_entry is not None
        assert ledger_entry.quantity_change == -25.0
        assert ledger_entry.balance_after == 75.0

        # 6. Prevent Duplicate Validation
        with pytest.raises(ValueError, match="already been validated"):
            DeliveryService.validate_delivery(delivery.id, user_id=manager_user_id)


def test_delivery_insufficient_stock_prevention(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)

        # Available is 100, try to deliver 150
        oversized_delivery = DeliveryService.create_delivery(
            customer_name='Large Corp',
            source_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 150.0}],
            user_id=manager_user_id
        )

        with pytest.raises(InsufficientStockError):
            DeliveryService.validate_delivery(oversized_delivery.id, user_id=manager_user_id)

        # Ensure stock remained unchanged
        assert product.total_stock == 100.0


def test_delivery_custom_quantity_done(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)
        initial_stock = product.total_stock  # 100.0

        delivery = DeliveryService.create_delivery(
            customer_name='Beta Industries',
            source_location_id=main_stock.id,
            lines=[{'product_id': product.id, 'demand': 30.0}],
            user_id=manager_user_id
        )
        move_id = delivery.moves[0].id

        # Deliver partial (e.g., 20 units)
        DeliveryService.validate_delivery(
            delivery.id,
            user_id=manager_user_id,
            quantities_done={move_id: 20.0}
        )
        assert delivery.status == 'done'
        assert product.total_stock == initial_stock - 20.0  # 80.0
