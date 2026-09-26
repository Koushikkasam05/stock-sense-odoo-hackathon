from app.extensions import db
from app.models.product import Product
from app.models.ledger import StockLedgerEntry
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.services.product_service import ProductService
from app.services.warehouse_service import WarehouseService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.services.adjustment_service import AdjustmentService

def test_notification_lifecycle(app, manager_user_id):
    with app.app_context():
        # Create notification
        notif1 = NotificationService.create_notification(
            title="Shortage Alert",
            message="Stock is low for item X",
            notification_type="warning",
            user_id=manager_user_id
        )
        assert notif1.id is not None
        assert notif1.is_read is False

        # Attempting to duplicate same unread notification should return existing
        notif2 = NotificationService.create_notification(
            title="Shortage Alert",
            message="Stock is low for item X",
            notification_type="warning",
            user_id=manager_user_id
        )
        assert notif1.id == notif2.id

        # Verify unread count
        unread = NotificationService.get_user_notifications(user_id=manager_user_id, unread_only=True)
        assert len(unread) == 1

        # Mark as read
        ok = NotificationService.mark_as_read(notif1.id, user_id=manager_user_id)
        assert ok is True
        assert NotificationService.get_user_notifications(user_id=manager_user_id, unread_only=True) == []

def test_all_operations_produce_ledger_entries(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']

        wh2 = WarehouseService.create_warehouse(name='West Distribution Hub', code='WH-WEST')
        west_stock = wh2.locations.filter_by(location_type='internal').first()

        # 1. Product creation with initial stock -> creates 'initial_stock' ledger entry
        prod = ProductService.create_product(
            name='Precision Multimeter',
            sku='ELEC-DMM-001',
            uom='Units',
            min_stock_level=10.0,
            initial_stock=50.0,
            initial_location_id=main_stock.id,
            user_id=manager_user_id
        )
        e1 = StockLedgerEntry.query.filter_by(product_id=prod.id, movement_type='initial_stock').first()
        assert e1 is not None
        assert e1.quantity_change == 50.0
        assert e1.balance_after == 50.0

        # 2. Receipt validation -> creates 'receipt' ledger entry
        receipt = ReceiptService.create_receipt(
            supplier_name='Tech Imports',
            dest_location_id=main_stock.id,
            lines=[{'product_id': prod.id, 'demand': 20.0}],
            user_id=manager_user_id
        )
        ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)
        e2 = StockLedgerEntry.query.filter_by(reference_document=receipt.name, movement_type='receipt').first()
        assert e2 is not None
        assert e2.quantity_change == 20.0
        assert e2.balance_after == 70.0

        # 3. Delivery validation -> creates 'delivery' ledger entry
        delivery = DeliveryService.create_delivery(
            customer_name='Client A',
            source_location_id=main_stock.id,
            lines=[{'product_id': prod.id, 'demand': 15.0}],
            user_id=manager_user_id
        )
        DeliveryService.validate_delivery(delivery.id, user_id=manager_user_id)
        e3 = StockLedgerEntry.query.filter_by(reference_document=delivery.name, movement_type='delivery').first()
        assert e3 is not None
        assert e3.quantity_change == -15.0
        assert e3.balance_after == 55.0

        # 4. Transfer validation -> creates 'transfer_out' and 'transfer_in' ledger entries
        transfer = TransferService.create_transfer(
            source_location_id=main_stock.id,
            dest_location_id=west_stock.id,
            lines=[{'product_id': prod.id, 'demand': 10.0}],
            user_id=manager_user_id
        )
        TransferService.validate_transfer(transfer.id, user_id=manager_user_id)
        t_out = StockLedgerEntry.query.filter_by(reference_document=transfer.name, movement_type='transfer_out').first()
        t_in = StockLedgerEntry.query.filter_by(reference_document=transfer.name, movement_type='transfer_in').first()
        assert t_out is not None and t_out.quantity_change == -10.0 and t_out.balance_after == 45.0
        assert t_in is not None and t_in.quantity_change == 10.0 and t_in.balance_after == 10.0

        # 5. Inventory adjustment -> creates 'adjustment_loss' or 'adjustment_gain' ledger entry
        adj = AdjustmentService.apply_adjustment(
            location_id=main_stock.id,
            product_id=prod.id,
            counted_quantity=42.0,  # Sys was 45 -> -3
            reason="Damaged unit inspection",
            user_id=manager_user_id
        )
        e5 = StockLedgerEntry.query.filter_by(reference_document=adj.name, movement_type='adjustment_loss').first()
        assert e5 is not None
        assert e5.quantity_change == -3.0
        assert e5.balance_after == 42.0
