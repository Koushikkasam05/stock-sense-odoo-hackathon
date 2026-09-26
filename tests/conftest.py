import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.services.warehouse_service import WarehouseService
from app.services.auth_service import AuthService
from app.services.product_service import ProductService

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        WarehouseService.ensure_default_locations()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def manager_user_id(app):
    with app.app_context():
        user = AuthService.register_user(
            username='testmanager',
            email='manager@test.com',
            password='password123',
            full_name='Test Manager',
            role='inventory_manager'
        )
        return user.id

@pytest.fixture
def sample_product_id(app, manager_user_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        cat = ProductService.get_or_create_category('Test Category')
        product = ProductService.create_product(
            name='Test Widget',
            sku='WIDGET-001',
            category_id=cat.id,
            uom='Units',
            min_stock_level=10.0,
            initial_stock=100.0,
            initial_location_id=locs['main_stock'].id,
            user_id=manager_user_id
        )
        return product.id
