import pytest
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.warehouse import Warehouse, Location
from app.models.ledger import StockLedgerEntry
from app.models.operation import StockPicking
from app.services.auth_service import AuthService
from app.services.warehouse_service import WarehouseService
from app.services.product_service import ProductService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.services.adjustment_service import AdjustmentService
from app.services.stock_service import StockService
from app.services.dashboard_service import DashboardService

def test_complete_business_audit_simulation(app, client):
    """
    Executes the comprehensive 19-step business logic audit simulation for StockSense.
    """
    with app.app_context():
        # Setup Default Warehouses & Locations
        locs = WarehouseService.ensure_default_locations()
        main_stock_id = locs['main_stock'].id
        prod_floor_id = locs['prod_floor'].id
        main_wh_id = locs['warehouse'].id

        # Step 1: Authentication & User Setup
        manager = AuthService.register_user(
            username='auditor_mgr',
            email='auditor@stocksense.test',
            password='Password123!',
            full_name='Audit Manager',
            role='inventory_manager'
        )
        staff = AuthService.register_user(
            username='auditor_staff',
            email='staff_auditor@stocksense.test',
            password='Password123!',
            full_name='Warehouse Operator',
            role='warehouse_staff'
        )
        manager_id = manager.id
        staff_id = staff.id

        auth_user = AuthService.authenticate_user('auditor_mgr', 'Password123!')
        assert auth_user is not None
        assert auth_user.is_manager is True

    # Login to HTTP client session as Manager
    login_resp = client.post('/auth/login', data={
        'identifier': 'auditor_mgr',
        'password': 'Password123!'
    }, follow_redirects=True)
    assert login_resp.status_code == 200

    with app.app_context():
        # Step 2: Open Dashboard
        initial_kpis = DashboardService.get_kpis()
        assert initial_kpis is not None

        # Step 3: Create or inspect a Steel Rod product
        cat = ProductService.get_or_create_category('Raw Materials', 'Industrial metal and raw stock')
        steel_rod = ProductService.create_product(
            name='Steel Rod 20mm',
            sku='STL-ROD-20MM',
            category_id=cat.id,
            uom='Meters',
            min_stock_level=80.0,  # Min threshold set to 80 to test low-stock later
            initial_stock=0.0,
            user_id=manager_id
        )
        prod_id = steel_rod.id
        assert steel_rod.total_stock == 0.0
        assert steel_rod.stock_status == 'out_of_stock'

        # Step 4: Receive 100 units from Supplier into Main Warehouse (Main Stock)
        receipt = ReceiptService.create_receipt(
            supplier_name='Apex Steel Mills Ltd',
            dest_location_id=main_stock_id,
            lines=[{'product_id': prod_id, 'demand': 100.0}],
            notes='Initial shipment of 20mm steel rods',
            user_id=manager_id
        )
        ReceiptService.validate_receipt(receipt.id, user_id=manager_id)

        # Step 5: Verify stock increases by 100
        steel_rod = db.session.get(Product, prod_id)
        assert StockService.get_location_stock(prod_id, main_stock_id) == 100.0
        assert steel_rod.total_stock == 100.0

        # Step 6: Transfer 30 units from Main Warehouse to Production Floor
        transfer = TransferService.create_transfer(
            source_location_id=main_stock_id,
            dest_location_id=prod_floor_id,
            lines=[{'product_id': prod_id, 'demand': 30.0}],
            notes='Material requisition for production batch #88',
            user_id=manager_id
        )
        TransferService.validate_transfer(transfer.id, user_id=manager_id)

        # Step 7: Verify source decreases by 30
        assert StockService.get_location_stock(prod_id, main_stock_id) == 70.0

        # Step 8: Verify destination increases by 30
        assert StockService.get_location_stock(prod_id, prod_floor_id) == 30.0

        # Step 9: Verify total company stock remains unchanged (Invariance)
        assert steel_rod.total_stock == 100.0

        # Step 10: Deliver 20 units to Customer
        delivery = DeliveryService.create_delivery(
            customer_name='Metro Construction Corp',
            source_location_id=main_stock_id,
            lines=[{'product_id': prod_id, 'demand': 20.0}],
            notes='Customer delivery order #DO-441',
            user_id=manager_id
        )
        DeliveryService.validate_delivery(delivery.id, user_id=manager_id)

        # Step 11: Verify stock decreases by 20
        assert StockService.get_location_stock(prod_id, main_stock_id) == 50.0
        assert steel_rod.total_stock == 80.0

        # Step 12: Perform physical stock adjustment of -3 units (Count 47 at Main Stock)
        adj = AdjustmentService.apply_adjustment(
            location_id=main_stock_id,
            product_id=prod_id,
            counted_quantity=47.0,  # Sys was 50 -> delta -3
            reason='Physical stock count audit - damaged rods discarded',
            user_id=manager_id
        )

        # Step 13: Verify stock changes by 3
        assert StockService.get_location_stock(prod_id, main_stock_id) == 47.0
        assert StockService.get_location_stock(prod_id, prod_floor_id) == 30.0
        assert steel_rod.total_stock == 77.0  # (47 in main_stock + 30 in prod_floor)

        # Step 14: Open Stock Ledger & Step 15: Verify all four movements exist
        ledger_entries = StockLedgerEntry.query.filter_by(product_id=prod_id).order_by(StockLedgerEntry.id.asc()).all()
        movement_types = [e.movement_type for e in ledger_entries]
        assert 'receipt' in movement_types
        assert 'transfer_out' in movement_types
        assert 'transfer_in' in movement_types
        assert 'delivery' in movement_types
        assert 'adjustment_loss' in movement_types

        # Step 16: Verify dashboard KPIs reflect the final state
        kpis = DashboardService.get_kpis()
        assert kpis['total_products'] >= 1
        assert kpis['pending_receipts'] == 0
        assert kpis['pending_deliveries'] == 0
        assert kpis['scheduled_transfers'] == 0

        # Step 17: Verify low-stock alert behavior (Min threshold is 80, current stock is 77 -> Low Stock Alert)
        assert steel_rod.stock_status == 'low_stock'
        assert steel_rod.is_low_stock is True

        alerts = DashboardService.get_low_and_out_of_stock_alerts()
        alert = next((a for a in alerts if a['sku'] == steel_rod.sku), None)
        assert alert is not None
        assert alert['is_low_stock'] is True
        assert alert['current_stock'] == 77.0

        # Step 18: Verify filters
        filtered_receipts = DashboardService.filter_ledger_entries_paginated(
            product_id=prod_id, movement_type='receipt'
        )
        assert filtered_receipts.total == 1
        assert filtered_receipts.items[0].quantity_change == 100.0

        filtered_transfers = DashboardService.filter_ledger_entries_paginated(
            product_id=prod_id, movement_type='transfer_out'
        )
        assert filtered_transfers.total == 1
        assert filtered_transfers.items[0].quantity_change == -30.0

        filtered_adjustments = DashboardService.filter_ledger_entries_paginated(
            product_id=prod_id, movement_type='adjustment_loss'
        )
        assert filtered_adjustments.total == 1
        assert filtered_adjustments.items[0].quantity_change == -3.0

        # Step 19: Verify user permissions
        user_manager = db.session.get(User, manager_id)
        user_staff = db.session.get(User, staff_id)
        assert user_manager.is_manager is True
        assert user_staff.is_manager is False

    # Log in as Warehouse Staff
    client.get('/auth/logout')
    client.post('/auth/login', data={
        'identifier': 'auditor_staff',
        'password': 'Password123!'
    }, follow_redirects=True)

    # Warehouse staff denied access to manager routes
    denied_resp = client.get('/products/new', follow_redirects=True)
    assert b'Access denied' in denied_resp.data

    denied_wh_resp = client.post('/warehouses/new', data={
        'name': 'Unauthorized WH',
        'code': 'WH-UNAUTH'
    }, follow_redirects=True)
    assert b'Access denied' in denied_wh_resp.data
