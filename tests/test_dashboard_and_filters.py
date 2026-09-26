import pytest
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.product import Product, ProductCategory
from app.models.warehouse import Warehouse, Location
from app.models.ledger import StockLedgerEntry
from app.services.warehouse_service import WarehouseService
from app.services.product_service import ProductService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.services.adjustment_service import AdjustmentService
from app.services.dashboard_service import DashboardService

def test_dashboard_kpi_and_alerts_accuracy(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        cat1 = ProductService.get_or_create_category('Pipes & Tubes')
        cat2 = ProductService.get_or_create_category('Fittings')

        # Create 3 products with different stock levels
        # 1. Normal in-stock product (100 > min 10)
        p_in = ProductService.create_product(
            name='Steel Pipe 2 inch',
            sku='PIPE-ST-02',
            category_id=cat1.id,
            uom='Meters',
            min_stock_level=10.0,
            initial_stock=100.0,
            initial_location_id=main_stock.id,
            user_id=manager_user_id
        )

        # 2. Low-stock product (5 <= min 15)
        p_low = ProductService.create_product(
            name='Copper Elbow 90deg',
            sku='FIT-ELB-90',
            category_id=cat2.id,
            uom='Pieces',
            min_stock_level=15.0,
            initial_stock=5.0,
            initial_location_id=main_stock.id,
            user_id=manager_user_id
        )

        # 3. Out-of-stock product (0 stock)
        p_out = ProductService.create_product(
            name='Brass Valve 1 inch',
            sku='VLV-BRS-01',
            category_id=cat2.id,
            uom='Units',
            min_stock_level=5.0,
            initial_stock=0.0,
            user_id=manager_user_id
        )

        # Create 1 draft receipt and 1 draft delivery
        rec = ReceiptService.create_receipt(
            supplier_name='Pipe Works',
            dest_location_id=main_stock.id,
            lines=[{'product_id': p_out.id, 'demand': 20.0}],
            user_id=manager_user_id
        )

        deli = DeliveryService.create_delivery(
            customer_name='BuildCo',
            source_location_id=main_stock.id,
            lines=[{'product_id': p_in.id, 'demand': 10.0}],
            user_id=manager_user_id
        )

        # Verify KPIs
        kpis = DashboardService.get_kpis()
        assert kpis['total_products'] == 3
        assert kpis['in_stock_products'] == 1
        assert kpis['low_stock_products'] == 1
        assert kpis['out_of_stock_products'] == 1
        assert kpis['pending_receipts'] == 1
        assert kpis['pending_deliveries'] == 1
        assert kpis['total_warehouses'] >= 1

        # Verify Low Stock & Out of Stock Alerts
        alerts = DashboardService.get_low_and_out_of_stock_alerts()
        assert len(alerts) == 2
        alert_skus = [a['sku'] for a in alerts]
        assert 'FIT-ELB-90' in alert_skus
        assert 'VLV-BRS-01' in alert_skus
        assert 'PIPE-ST-02' not in alert_skus

        low_item = next(a for a in alerts if a['sku'] == 'FIT-ELB-90')
        assert low_item['is_low_stock'] is True
        assert low_item['is_out_of_stock'] is False

        out_item = next(a for a in alerts if a['sku'] == 'VLV-BRS-01')
        assert out_item['is_out_of_stock'] is True
        assert out_item['is_low_stock'] is False


def test_operation_and_ledger_filters(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        prod_floor = locs['prod_floor']
        wh = locs['warehouse']

        prod = ProductService.create_product(
            name='Galvanized Sheet',
            sku='MET-SHT-GALV',
            uom='Sheets',
            min_stock_level=10.0,
            initial_stock=50.0,
            initial_location_id=main_stock.id,
            user_id=manager_user_id
        )

        # Receipt
        receipt = ReceiptService.create_receipt(
            supplier_name='Metal Source Ltd',
            dest_location_id=main_stock.id,
            lines=[{'product_id': prod.id, 'demand': 20.0}],
            user_id=manager_user_id
        )
        ReceiptService.validate_receipt(receipt.id, user_id=manager_user_id)

        # Transfer
        transfer = TransferService.create_transfer(
            source_location_id=main_stock.id,
            dest_location_id=prod_floor.id,
            lines=[{'product_id': prod.id, 'demand': 10.0}],
            user_id=manager_user_id
        )
        TransferService.validate_transfer(transfer.id, user_id=manager_user_id)

        # 1. Filter Operations by doc_type and status
        ops_receipt = DashboardService.filter_operations(doc_type='receipt', status='done')
        assert len(ops_receipt) >= 1
        assert all(op.picking_type == 'receipt' for op in ops_receipt)

        ops_transfer = DashboardService.filter_operations(doc_type='transfer')
        assert len(ops_transfer) >= 1
        assert all(op.picking_type == 'transfer' for op in ops_transfer)

        # 2. Filter Operations by location
        ops_loc = DashboardService.filter_operations(location_id=prod_floor.id)
        assert len(ops_loc) >= 1

        # 3. Filter Ledger by Movement Type
        pag_receipt = DashboardService.filter_ledger_entries_paginated(movement_type='receipt', product_id=prod.id)
        assert pag_receipt.total == 1
        assert pag_receipt.items[0].movement_type == 'receipt'

        pag_transfer_in = DashboardService.filter_ledger_entries_paginated(movement_type='transfer_in', product_id=prod.id)
        assert pag_transfer_in.total == 1

        # 4. Filter Ledger by SKU search
        pag_search = DashboardService.filter_ledger_entries_paginated(sku='MET-SHT')
        assert pag_search.total >= 3  # initial_stock, receipt, transfer_out, transfer_in

        # 5. Filter Ledger by Warehouse
        pag_wh = DashboardService.filter_ledger_entries_paginated(warehouse_id=wh.id)
        assert pag_wh.total >= 3


def test_health_check_endpoint(app, client):
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'healthy'
    assert data['database'] == 'connected'
    assert data['version'] == '1.0.0'

