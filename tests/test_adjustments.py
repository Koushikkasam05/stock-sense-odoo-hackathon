from app.extensions import db
from app.models.product import Product
from app.services.adjustment_service import AdjustmentService
from app.services.stock_service import StockService
from app.services.warehouse_service import WarehouseService
from app.services.dashboard_service import DashboardService
from app.models.ledger import StockLedgerEntry

def test_inventory_adjustment_loss_and_gain(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        product = db.session.get(Product, sample_product_id)

        # Sample product initial stock is 100
        # 1. Adjust down to 92 (Loss of 8)
        adj1 = AdjustmentService.apply_adjustment(
            location_id=main_stock.id,
            product_id=product.id,
            counted_quantity=92.0,
            reason='Damage write-off',
            user_id=manager_user_id
        )
        assert adj1.status == 'done'
        assert StockService.get_location_stock(product.id, main_stock.id) == 92.0

        loss_entry = StockLedgerEntry.query.filter_by(
            product_id=product.id,
            movement_type='adjustment_loss',
            reference_document=adj1.name
        ).first()
        assert loss_entry is not None
        assert loss_entry.quantity_change == -8.0
        assert loss_entry.balance_after == 92.0

        # 2. Adjust up to 105 (Gain of 13)
        adj2 = AdjustmentService.apply_adjustment(
            location_id=main_stock.id,
            product_id=product.id,
            counted_quantity=105.0,
            reason='Found uncounted stock',
            user_id=manager_user_id
        )
        assert adj2.status == 'done'
        assert StockService.get_location_stock(product.id, main_stock.id) == 105.0

        gain_entry = StockLedgerEntry.query.filter_by(
            product_id=product.id,
            movement_type='adjustment_gain',
            reference_document=adj2.name
        ).first()
        assert gain_entry is not None
        assert gain_entry.quantity_change == 13.0
        assert gain_entry.balance_after == 105.0

def test_dashboard_kpis_and_alerts(app, manager_user_id, sample_product_id):
    with app.app_context():
        product = db.session.get(Product, sample_product_id)
        kpis = DashboardService.get_kpis()
        assert kpis['total_products'] >= 1
        assert kpis['in_stock_products'] >= 1

        alerts = DashboardService.get_low_and_out_of_stock_alerts()
        # Sample product has 100 > min 10 -> not in alert
        assert len([a for a in alerts if a['sku'] == product.sku]) == 0

        # Now adjust down to 5 (below min 10) -> should trigger alert
        locs = WarehouseService.ensure_default_locations()
        AdjustmentService.apply_adjustment(
            location_id=locs['main_stock'].id,
            product_id=product.id,
            counted_quantity=5.0,
            user_id=manager_user_id
        )

        new_alerts = DashboardService.get_low_and_out_of_stock_alerts()
        low_alert = next((a for a in new_alerts if a['sku'] == product.sku), None)
        assert low_alert is not None
        assert low_alert['is_low_stock'] is True
        assert low_alert['current_stock'] == 5.0
