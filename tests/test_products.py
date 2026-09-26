import pytest
from app.extensions import db
from app.models.product import Product, ProductCategory, StockQuant
from app.models.ledger import StockLedgerEntry
from app.services.product_service import ProductService
from app.services.warehouse_service import WarehouseService
from app.services.auth_service import AuthService

def test_product_creation_and_initial_stock(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Electronics', 'Electronic components and devices')

        # 1. Create product without initial stock
        p1 = ProductService.create_product(
            name='Resistor 10k',
            sku='ELEC-RES-10K',
            category_id=cat.id,
            uom='Pieces',
            min_stock_level=50.0,
            initial_stock=0.0,
            user_id=manager_user_id
        )
        assert p1.id is not None
        assert p1.total_stock == 0.0
        assert p1.stock_status == 'out_of_stock'
        assert p1.is_out_of_stock is True

        # 2. Create product with initial stock
        p2 = ProductService.create_product(
            name='Capacitor 100uF',
            sku='ELEC-CAP-100U',
            category_id=cat.id,
            uom='Pieces',
            min_stock_level=20.0,
            initial_stock=100.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )
        assert p2.total_stock == 100.0
        assert p2.stock_status == 'in_stock'

        # Check ledger entry for initial stock
        entry = StockLedgerEntry.query.filter_by(product_id=p2.id, movement_type='initial_stock').first()
        assert entry is not None
        assert entry.quantity_change == 100.0
        assert entry.balance_after == 100.0


def test_product_duplicate_sku_and_validation(app, manager_user_id):
    with app.app_context():
        ProductService.create_product(
            name='Hex Bolt M8',
            sku='FAST-BOLT-M8',
            uom='Units',
            min_stock_level=100.0,
            user_id=manager_user_id
        )

        # Duplicate SKU (case-insensitive) should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            ProductService.create_product(
                name='Hex Bolt M8 Zinc',
                sku='fast-bolt-m8',
                uom='Units',
                min_stock_level=50.0,
                user_id=manager_user_id
            )


def test_product_edit(app, manager_user_id, sample_product_id):
    with app.app_context():
        updated = ProductService.update_product(
            product_id=sample_product_id,
            name='Test Widget Premium',
            category_id=None,
            uom='Box',
            min_stock_level=15.0,
            description='Updated widget specifications',
            is_active=False
        )

        assert updated.name == 'Test Widget Premium'
        assert updated.uom == 'Box'
        assert updated.min_stock_level == 15.0
        assert updated.is_active is False

        # Non-existent product update should fail
        with pytest.raises(ValueError, match="not found"):
            ProductService.update_product(
                product_id=999999,
                name='Ghost Product',
                category_id=None,
                uom='Units',
                min_stock_level=10.0,
                description=None
            )


def test_product_web_routes_and_export(app, client, manager_user_id, sample_product_id):
    # Log in as manager
    with client.session_transaction() as sess:
        sess['_user_id'] = str(manager_user_id)
        sess['_fresh'] = True

    # 1. Product Index page
    resp = client.get('/products/')
    assert resp.status_code == 200
    assert b'Test Widget' in resp.data

    # 2. Product Detail page
    detail_resp = client.get(f'/products/{sample_product_id}')
    assert detail_resp.status_code == 200
    assert b'WIDGET-001' in detail_resp.data

    # 3. Product CSV Export
    csv_resp = client.get('/products/export/csv')
    assert csv_resp.status_code == 200
    assert csv_resp.headers['Content-Type'] == 'text/csv; charset=utf-8'
    assert b'SKU Code,Product Name,Category' in csv_resp.data
    assert b'WIDGET-001' in csv_resp.data
