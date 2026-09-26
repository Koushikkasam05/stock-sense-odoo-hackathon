import pytest
from app.extensions import db
from app.models.user import User
from app.models.product import Product, ProductCategory
from app.models.warehouse import Warehouse, Location
from app.models.audit import AuditLog
from app.services.auth_service import AuthService
from app.services.product_service import ProductService
from app.services.warehouse_service import WarehouseService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.services.movement_service import MovementAnalysisService
from app.services.demand_service import DemandAnalysisService
from app.services.dashboard_service import DashboardService
from app.services.audit_service import AuditService

def test_password_complexity_validation(app):
    with app.app_context():
        # Missing uppercase
        v1, _ = AuthService.validate_password_complexity('password123!')
        assert v1 is False

        # Missing lowercase
        v2, _ = AuthService.validate_password_complexity('PASSWORD123!')
        assert v2 is False

        # Missing number
        v3, _ = AuthService.validate_password_complexity('PasswordSpecial!')
        assert v3 is False

        # Missing special char
        v4, _ = AuthService.validate_password_complexity('Password1234')
        assert v4 is False

        # Too short (< 8 chars)
        v5, _ = AuthService.validate_password_complexity('P1!a')
        assert v5 is False

        # Valid password
        v6, msg = AuthService.validate_password_complexity('SecurePassword123!')
        assert v6 is True
        assert msg == ""


def test_mobile_otp_authentication_flow(app, client):
    with app.app_context():
        user = AuthService.register_user(
            username='mobileuser',
            email='mobile@test.com',
            mobile_number='+15559998888',
            password='SecurePass123!',
            full_name='Mobile User',
            role='warehouse_staff'
        )

        # 1. Request mobile OTP
        ok, msg, otp = AuthService.request_mobile_login_otp('+15559998888')
        assert ok is True
        assert otp is not None
        assert len(otp) == 6

        # 2. Verify invalid OTP
        bad_ok, bad_msg, _ = AuthService.verify_mobile_login_otp('+15559998888', '000000')
        assert bad_ok is False

        # 3. Verify valid OTP
        good_ok, _, authed_user = AuthService.verify_mobile_login_otp('+15559998888', otp)
        assert good_ok is True
        assert authed_user.id == user.id

        # 4. Re-verify used OTP fails
        reused_ok, _, _ = AuthService.verify_mobile_login_otp('+15559998888', otp)
        assert reused_ok is False


def test_critical_and_stock_status_calculation(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Electronics Testing')

        # Product with 0 stock -> out_of_stock
        p_zero = ProductService.create_product(
            name='Zero Stock Item',
            sku='ZERO-001',
            category_id=cat.id,
            min_stock_level=20.0,
            initial_stock=0.0,
            user_id=manager_user_id
        )
        assert p_zero.stock_status == 'out_of_stock'
        assert p_zero.is_out_of_stock is True

        # Product with stock <= 25% of min_stock -> critical
        p_crit = ProductService.create_product(
            name='Critical Stock Item',
            sku='CRIT-001',
            category_id=cat.id,
            min_stock_level=20.0,
            initial_stock=4.0,  # 4 <= 20 * 0.25 (5)
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )
        assert p_crit.stock_status == 'critical'
        assert p_crit.is_critical_stock is True

        # Product with stock <= min_stock but > 25% -> low_stock
        p_low = ProductService.create_product(
            name='Low Stock Item',
            sku='LOW-001',
            category_id=cat.id,
            min_stock_level=20.0,
            initial_stock=15.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )
        assert p_low.stock_status == 'low_stock'
        assert p_low.is_low_stock is True

        # Product with stock > min_stock -> in_stock
        p_in = ProductService.create_product(
            name='In Stock Item',
            sku='INSTOCK-001',
            category_id=cat.id,
            min_stock_level=20.0,
            initial_stock=50.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )
        assert p_in.stock_status == 'in_stock'


def test_movement_and_demand_services(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Fast Goods')

        product = ProductService.create_product(
            name='Velocity Test Product',
            sku='VELO-001',
            category_id=cat.id,
            min_stock_level=10.0,
            initial_stock=200.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )

        # Before moves: No Movement & Insufficient data
        mov_initial = MovementAnalysisService.get_movement_status(product.id)
        assert mov_initial['status'] in ['No Movement', 'Normal Moving']

        # Dispatch 60 units via delivery
        deliv = DeliveryService.create_delivery(
            customer_name='Acme MegaCorp',
            source_location_id=locs['main_stock'].id,
            lines=[{'product_id': product.id, 'demand': 60.0}],
            user_id=manager_user_id
        )
        DeliveryService.validate_delivery(deliv.id, user_id=manager_user_id)

        # After high volume delivery: Fast Moving and High Demand
        mov_after = MovementAnalysisService.get_movement_status(product.id)
        assert mov_after['status'] == 'Fast Moving'

        dem_after = DemandAnalysisService.get_demand_status(product.id)
        assert dem_after['status'] == 'High Demand'


def test_global_search_api(app, client, manager_user_id):
    with app.app_context():
        WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Searchable Category')
        ProductService.create_product(
            name='Super Secret Scanner',
            sku='SCAN-999',
            category_id=cat.id,
            min_stock_level=5.0,
            initial_stock=10.0,
            user_id=manager_user_id
        )

        # Login client
        user = db.session.get(User, manager_user_id)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    # Call Global Search API
    resp = client.get('/search/api?q=Scanner')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_found'] >= 1
    assert data['products'][0]['name'] == 'Super Secret Scanner'
    assert data['products'][0]['sku'] == 'SCAN-999'

    # Call Search Results HTML Page
    html_resp = client.get('/search/?q=Scanner')
    assert html_resp.status_code == 200
    assert b'Super Secret Scanner' in html_resp.data


def test_audit_logging_mechanism(app, manager_user_id):
    with app.app_context():
        AuditService.log_event(
            action='SECURITY_TEST_ACTION',
            resource_type='system',
            resource_id='TEST-01',
            details='Test audit log entry',
            user_id=manager_user_id
        )

        log_entry = AuditLog.query.filter_by(action='SECURITY_TEST_ACTION').first()
        assert log_entry is not None
        assert log_entry.resource_type == 'system'
        assert log_entry.resource_id == 'TEST-01'
        assert log_entry.user_id == manager_user_id


def test_inventory_analytics_service_and_routes(app, client, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Analytics Category')
        ProductService.create_product(
            name='Analytics Test Product',
            sku='ANALYTICS-001',
            category_id=cat.id,
            min_stock_level=10.0,
            initial_stock=25.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )

        # Service-level verification
        analytics = DashboardService.get_inventory_analytics()
        assert 'total_valuation' in analytics
        assert analytics['total_valuation'] >= 25.0
        assert 'categories' in analytics
        assert 'warehouses' in analytics
        assert 'trends' in analytics
        assert len(analytics['trends']['labels']) == 14

        # Login client
        user = db.session.get(User, manager_user_id)
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    # Test Analytics Web Route
    resp = client.get('/analytics')
    assert resp.status_code == 200
    assert b'Executive Inventory Analytics' in resp.data

    # Test Analytics JSON API
    api_resp = client.get('/analytics/api')
    assert api_resp.status_code == 200
    data = api_resp.get_json()
    assert data['success'] is True
    assert 'data' in data
    assert 'trends' in data['data']

