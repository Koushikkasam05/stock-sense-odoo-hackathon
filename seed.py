from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.warehouse import Warehouse, Location
from app.models.product import ProductCategory, Product, StockQuant
from app.models.operation import StockPicking
from app.models.notification import Notification
from app.services.warehouse_service import WarehouseService
from app.services.auth_service import AuthService
from app.services.product_service import ProductService
from app.services.receipt_service import ReceiptService
from app.services.delivery_service import DeliveryService
from app.services.transfer_service import TransferService
from app.services.adjustment_service import AdjustmentService
from app.services.notification_service import NotificationService

def seed_database():
    app = create_app()
    with app.app_context():
        print("[+] Seeding realistic StockSense database...")
        db.create_all()

        # 1. Virtual & Default Locations
        locs = WarehouseService.ensure_default_locations()

        # 2. Warehouses
        main_wh = Warehouse.query.filter_by(code='WH-HYD').first()
        if not main_wh:
            main_wh = WarehouseService.create_warehouse(
                name='Main Warehouse (Hyderabad)',
                code='WH-HYD',
                address='Plot 44, Hi-Tech City Logistics Zone, Hyderabad'
            )

        prod_wh = Warehouse.query.filter_by(code='WH-BLR').first()
        if not prod_wh:
            prod_wh = WarehouseService.create_warehouse(
                name='Bangalore Central Hub',
                code='WH-BLR',
                address='Electronic City Phase II, Bangalore'
            )

        sec_wh = Warehouse.query.filter_by(code='WH-CHN').first()
        if not sec_wh:
            sec_wh = WarehouseService.create_warehouse(
                name='Chennai Port Distribution',
                code='WH-CHN',
                address='Harbor Expressway Hub, Chennai'
            )

        # 3. Locations inside Warehouses (with parent-child hierarchy)
        rack_a = Location.query.filter_by(code='WH-HYD/RACK-A').first()
        if not rack_a:
            rack_a = WarehouseService.create_location(
                warehouse_id=main_wh.id,
                name='Rack A (Heavy Metals)',
                code='WH-HYD/RACK-A',
                location_type='internal'
            )

        rack_b = Location.query.filter_by(code='WH-HYD/RACK-B').first()
        if not rack_b:
            rack_b = WarehouseService.create_location(
                warehouse_id=main_wh.id,
                name='Rack B (Furniture)',
                code='WH-HYD/RACK-B',
                location_type='internal'
            )

        prod_floor = Location.query.filter_by(code='WH-BLR/FLOOR').first()
        if not prod_floor:
            prod_floor = WarehouseService.create_location(
                warehouse_id=prod_wh.id,
                name='Assembly Floor',
                code='WH-BLR/FLOOR',
                location_type='internal'
            )

        dispatch_area = Location.query.filter_by(code='WH-CHN/DISPATCH').first()
        if not dispatch_area:
            dispatch_area = WarehouseService.create_location(
                warehouse_id=sec_wh.id,
                name='Export Dispatch Bay',
                code='WH-CHN/DISPATCH',
                location_type='internal'
            )

        # 4. Users (Manager & Staff with strict complexity & mobile)
        manager = User.query.filter_by(username='manager').first()
        if not manager:
            manager = AuthService.register_user(
                username='manager',
                email='manager@stocksense.com',
                mobile_number='+15550109999',
                password='Password123!',
                full_name='Alex Rivera (Manager)',
                role='inventory_manager'
            )
            print("  [OK] Created Manager user: manager / Password123! (+15550109999)")

        staff = User.query.filter_by(username='staff').first()
        if not staff:
            staff = AuthService.register_user(
                username='staff',
                email='staff@stocksense.com',
                mobile_number='+15550108888',
                password='Password123!',
                full_name='Jordan Lee (Staff)',
                role='warehouse_staff'
            )
            print("  [OK] Created Staff user: staff / Password123! (+15550108888)")

        # 5. Product Categories
        cat_raw = ProductService.get_or_create_category('Raw Materials', 'Metals, rods, wire, timber')
        cat_elec = ProductService.get_or_create_category('Electronics', 'Laptops, sensors, circuit boards, peripherals')
        cat_furn = ProductService.get_or_create_category('Furniture', 'Chairs, desks, ergonomic workstations')
        cat_pack = ProductService.get_or_create_category('Packaging', 'Boxes, tape, corrugated wrap')
        cat_off = ProductService.get_or_create_category('Office Supplies', 'Stationery, paper, toner')

        # 6. Products with Varied Stock Levels & Categories
        # Fast-Moving Item (Laptop Pro 15)
        p_laptop = Product.query.filter_by(sku='ELEC-LAP-PRO15').first()
        if not p_laptop:
            p_laptop = ProductService.create_product(
                name='StockSense Laptop Pro 15"',
                sku='ELEC-LAP-PRO15',
                category_id=cat_elec.id,
                uom='Units',
                min_stock_level=20.0,
                description='High-performance enterprise laptop with 32GB RAM',
                initial_stock=120.0,
                initial_location_id=rack_a.id,
                user_id=manager.id
            )

        # Raw Steel Rods (Normal Stock)
        p_steel = Product.query.filter_by(sku='RAW-STEEL-ROD').first()
        if not p_steel:
            p_steel = ProductService.create_product(
                name='Steel Rod (10mm x 2m)',
                sku='RAW-STEEL-ROD',
                category_id=cat_raw.id,
                uom='Units',
                min_stock_level=25.0,
                description='High-tensile carbon steel reinforcement rod',
                initial_stock=100.0,
                initial_location_id=rack_a.id,
                user_id=manager.id
            )

        # Wooden Chair (Normal Stock)
        p_chair = Product.query.filter_by(sku='FURN-WOOD-CHR').first()
        if not p_chair:
            p_chair = ProductService.create_product(
                name='Wooden Ergonomic Chair',
                sku='FURN-WOOD-CHR',
                category_id=cat_furn.id,
                uom='Units',
                min_stock_level=10.0,
                description='Solid oak finished wooden dining & desk chair',
                initial_stock=45.0,
                initial_location_id=rack_b.id,
                user_id=manager.id
            )

        # Office Table (Low Stock)
        p_table = Product.query.filter_by(sku='FURN-OFF-TBL').first()
        if not p_table:
            p_table = ProductService.create_product(
                name='Ergonomic Office Table',
                sku='FURN-OFF-TBL',
                category_id=cat_furn.id,
                uom='Units',
                min_stock_level=15.0,
                description='Adjustable height modular office work desk',
                initial_stock=6.0,  # Low Stock condition
                initial_location_id=rack_b.id,
                user_id=manager.id
            )

        # Copper Wire (Out of Stock)
        p_copper = Product.query.filter_by(sku='ELEC-COPPER-WIRE').first()
        if not p_copper:
            p_copper = ProductService.create_product(
                name='Insulated Copper Wire (100m Spool)',
                sku='ELEC-COPPER-WIRE',
                category_id=cat_elec.id,
                uom='Spools',
                min_stock_level=20.0,
                description='Multi-core insulated copper wiring spool',
                initial_stock=0.0,  # Out of stock condition
                initial_location_id=rack_a.id,
                user_id=manager.id
            )

        # Packaging Boxes (Normal Stock)
        p_box = Product.query.filter_by(sku='PACK-BOX-STD').first()
        if not p_box:
            p_box = ProductService.create_product(
                name='Heavy-Duty Packaging Box (Medium)',
                sku='PACK-BOX-STD',
                category_id=cat_pack.id,
                uom='Boxes',
                min_stock_level=50.0,
                description='Double-wall corrugated shipping carton',
                initial_stock=200.0,
                initial_location_id=dispatch_area.id,
                user_id=manager.id
            )

        # 7. Sample Operations (Receipts, Deliveries, Transfers, Adjustments)
        has_sample_ops = StockPicking.query.first() is not None
        if not has_sample_ops:
            # Validate Receipt of 50 Steel Rods
            rec1 = ReceiptService.create_receipt(
                supplier_name="National Steel Mills Ltd",
                dest_location_id=rack_a.id,
                lines=[{'product_id': p_steel.id, 'demand': 50.0}],
                notes="PO-40291 Raw material replenishment",
                user_id=staff.id
            )
            ReceiptService.validate_receipt(rec1.id, user_id=staff.id)

            # High-volume outgoing deliveries for Laptop to make it Fast-Moving & High Demand
            try:
                del_lap1 = DeliveryService.create_delivery(
                    customer_name="TechCorp Solutions Ltd",
                    source_location_id=rack_a.id,
                    lines=[{'product_id': p_laptop.id, 'demand': 25.0}],
                    notes="SO-9001 Corporate fleet rollout",
                    user_id=staff.id
                )
                DeliveryService.advance_status(del_lap1.id, 'ready', user_id=staff.id)
                DeliveryService.validate_delivery(del_lap1.id, user_id=staff.id)
            except Exception as e:
                print(f"  [Note] del_lap1 skipped: {e}")

            try:
                del_lap2 = DeliveryService.create_delivery(
                    customer_name="CloudNine Systems",
                    source_location_id=rack_a.id,
                    lines=[{'product_id': p_laptop.id, 'demand': 30.0}],
                    notes="SO-9002 Engineering team hardware upgrade",
                    user_id=staff.id
                )
                DeliveryService.advance_status(del_lap2.id, 'ready', user_id=staff.id)
                DeliveryService.validate_delivery(del_lap2.id, user_id=staff.id)
            except Exception as e:
                print(f"  [Note] del_lap2 skipped: {e}")

            # Pending Receipt for Copper
            ReceiptService.create_receipt(
                supplier_name="CopperTech Wiring Global",
                dest_location_id=rack_a.id,
                lines=[{'product_id': p_copper.id, 'demand': 60.0}],
                notes="PO-40315 Urgent restock for copper spools",
                user_id=manager.id
            )

            # Completed Delivery: 10 Chairs Delivered
            try:
                del1 = DeliveryService.create_delivery(
                    customer_name="Modern Living Interiors",
                    source_location_id=rack_b.id,
                    lines=[{'product_id': p_chair.id, 'demand': 10.0}],
                    notes="SO-8812 Commercial client delivery",
                    user_id=staff.id
                )
                DeliveryService.advance_status(del1.id, 'ready', user_id=staff.id)
                DeliveryService.validate_delivery(del1.id, user_id=staff.id)
            except Exception as e:
                print(f"  [Note] del1 skipped: {e}")

            # Internal Transfer: 30 Steel Rods from Hyderabad -> Bangalore Hub
            try:
                trans1 = TransferService.create_transfer(
                    source_location_id=rack_a.id,
                    dest_location_id=prod_floor.id,
                    lines=[{'product_id': p_steel.id, 'demand': 30.0}],
                    notes="Transfer raw steel rods for Bangalore fabrication line",
                    user_id=manager.id
                )
                TransferService.validate_transfer(trans1.id, user_id=manager.id)
            except Exception as e:
                print(f"  [Note] trans1 skipped: {e}")

            # Physical Count Inventory Adjustment: Box count 200 -> 195 (-5 variance)
            try:
                AdjustmentService.apply_adjustment(
                    location_id=dispatch_area.id,
                    product_id=p_box.id,
                    counted_quantity=195.0,
                    reason="Q3 Physical cycle count variance reconciliation",
                    user_id=manager.id
                )
            except Exception as e:
                print(f"  [Note] adjustment skipped: {e}")

        # 8. Seed Notifications
        if not Notification.query.first():
            NotificationService.create_notification(
                title="Out of Stock: Copper Wire",
                message="Product 'Insulated Copper Wire (100m Spool)' has reached 0 units on hand. Immediate reorder recommended.",
                notification_type="danger",
                user_id=manager.id
            )

            NotificationService.create_notification(
                title="Low Stock: Ergonomic Office Table",
                message="Product 'Ergonomic Office Table' has 6 units remaining (below safety threshold of 15).",
                notification_type="warning",
                user_id=manager.id
            )

            NotificationService.create_notification(
                title="Pending Receipt Awaiting Inspection",
                message="Incoming shipment from CopperTech Wiring Global (PO-40315) is scheduled for today.",
                notification_type="info",
                user_id=staff.id
            )

        print("[OK] Realistic demo data seeded successfully!")

if __name__ == '__main__':
    seed_database()
