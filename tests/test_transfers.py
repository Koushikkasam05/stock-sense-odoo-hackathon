import pytest
from app.extensions import db
from app.models.product import Product
from app.models.ledger import StockLedgerEntry
from app.services.warehouse_service import WarehouseService
from app.services.product_service import ProductService
from app.services.transfer_service import TransferService
from app.services.stock_service import StockService, InsufficientStockError

def test_internal_transfer_flow_and_invariance(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        prod_floor = locs['prod_floor']
        product = db.session.get(Product, sample_product_id)
        initial_company_stock = product.total_stock  # 100.0

        # 1. Create Transfer of 35 units from Main Stock to Production Floor
        transfer = TransferService.create_transfer(
            source_location_id=main_stock.id,
            dest_location_id=prod_floor.id,
            lines=[{'product_id': product.id, 'demand': 35.0}],
            notes='Supply to assembly line',
            user_id=manager_user_id
        )
        assert transfer.id is not None
        assert transfer.picking_type == 'transfer'
        assert transfer.status == 'draft'

        # 2. Validate Transfer
        TransferService.validate_transfer(transfer.id, user_id=manager_user_id)
        assert transfer.status == 'done'

        # 3. Verify Source Decreased and Destination Increased
        main_qty = StockService.get_location_stock(product.id, main_stock.id)
        prod_qty = StockService.get_location_stock(product.id, prod_floor.id)
        assert main_qty == 100.0 - 35.0  # 65.0
        assert prod_qty == 35.0

        # 4. Verify Total Company Stock is Unchanged (Invariant)
        assert product.total_stock == initial_company_stock  # 100.0

        # 5. Verify Paired Ledger Entries Created
        t_out = StockLedgerEntry.query.filter_by(
            reference_document=transfer.name,
            location_id=main_stock.id,
            movement_type='transfer_out'
        ).first()
        t_in = StockLedgerEntry.query.filter_by(
            reference_document=transfer.name,
            location_id=prod_floor.id,
            movement_type='transfer_in'
        ).first()

        assert t_out is not None and t_out.quantity_change == -35.0 and t_out.balance_after == 65.0
        assert t_in is not None and t_in.quantity_change == 35.0 and t_in.balance_after == 35.0

        # 6. Prevent Duplicate Execution
        with pytest.raises(ValueError, match="already been executed"):
            TransferService.validate_transfer(transfer.id, user_id=manager_user_id)


def test_transfer_rules_and_insufficient_stock(app, manager_user_id, sample_product_id):
    with app.app_context():
        locs = WarehouseService.ensure_default_locations()
        main_stock = locs['main_stock']
        prod_floor = locs['prod_floor']
        product = db.session.get(Product, sample_product_id)

        # Same source and destination must fail
        with pytest.raises(ValueError, match="cannot be the same"):
            TransferService.create_transfer(
                source_location_id=main_stock.id,
                dest_location_id=main_stock.id,
                lines=[{'product_id': product.id, 'demand': 10.0}],
                user_id=manager_user_id
            )

        # Over-demand transfer from main_stock (only 100 available)
        bad_transfer = TransferService.create_transfer(
            source_location_id=main_stock.id,
            dest_location_id=prod_floor.id,
            lines=[{'product_id': product.id, 'demand': 500.0}],
            user_id=manager_user_id
        )

        with pytest.raises(InsufficientStockError):
            TransferService.validate_transfer(bad_transfer.id, user_id=manager_user_id)
