from typing import Optional, List, Dict, Any
from app.extensions import db
from app.models.warehouse import Warehouse, Location
from app.models.product import StockQuant, Product

class WarehouseService:
    @staticmethod
    def ensure_default_locations() -> dict:
        """
        Ensures system default virtual locations and a primary default warehouse/location exist.
        Returns a dictionary of key location objects.
        """
        # Virtual Vendor Location
        vendor_loc = Location.query.filter_by(code='VEND-IN').first()
        if not vendor_loc:
            vendor_loc = Location(
                name='Vendors / Suppliers',
                code='VEND-IN',
                location_type='vendor',
                is_active=True
            )
            db.session.add(vendor_loc)

        # Virtual Customer Location
        customer_loc = Location.query.filter_by(code='CUST-OUT').first()
        if not customer_loc:
            customer_loc = Location(
                name='Customers / Outgoing',
                code='CUST-OUT',
                location_type='customer',
                is_active=True
            )
            db.session.add(customer_loc)

        # Virtual Loss / Scrap / Adjustment Location
        loss_loc = Location.query.filter_by(code='INV-LOSS').first()
        if not loss_loc:
            loss_loc = Location(
                name='Inventory Loss / Adjustment',
                code='INV-LOSS',
                location_type='loss',
                is_active=True
            )
            db.session.add(loss_loc)

        # Main Warehouse
        main_wh = Warehouse.query.filter_by(code='WH-MAIN').first()
        if not main_wh:
            main_wh = Warehouse(
                name='Main Central Warehouse',
                code='WH-MAIN',
                address='100 Logistics Blvd, Zone A',
                is_active=True
            )
            db.session.add(main_wh)
            db.session.flush()

        # Main Stock Location
        main_stock = Location.query.filter_by(code='WH-MAIN/STOCK').first()
        if not main_stock:
            main_stock = Location(
                warehouse_id=main_wh.id,
                name='Stock Floor',
                code='WH-MAIN/STOCK',
                location_type='internal',
                is_active=True
            )
            db.session.add(main_stock)

        # Production Floor Location
        prod_floor = Location.query.filter_by(code='WH-MAIN/PROD').first()
        if not prod_floor:
            prod_floor = Location(
                warehouse_id=main_wh.id,
                name='Production Floor',
                code='WH-MAIN/PROD',
                location_type='internal',
                is_active=True
            )
            db.session.add(prod_floor)

        db.session.commit()
        return {
            'vendor': vendor_loc,
            'customer': customer_loc,
            'loss': loss_loc,
            'warehouse': main_wh,
            'main_stock': main_stock,
            'prod_floor': prod_floor
        }

    @staticmethod
    def get_internal_locations() -> List[Location]:
        """Fetch all active internal storage locations."""
        return Location.query.filter_by(location_type='internal', is_active=True).all()

    @staticmethod
    def get_vendor_location() -> Location:
        WarehouseService.ensure_default_locations()
        return Location.query.filter_by(code='VEND-IN').first()

    @staticmethod
    def get_customer_location() -> Location:
        WarehouseService.ensure_default_locations()
        return Location.query.filter_by(code='CUST-OUT').first()

    @staticmethod
    def get_loss_location() -> Location:
        WarehouseService.ensure_default_locations()
        return Location.query.filter_by(code='INV-LOSS').first()

    @staticmethod
    def create_warehouse(name: str, code: str, address: Optional[str] = None) -> Warehouse:
        code_clean = code.strip().upper()
        if Warehouse.query.filter((Warehouse.code == code_clean) | (Warehouse.name == name.strip())).first():
            raise ValueError(f"Warehouse with name '{name}' or code '{code_clean}' already exists.")

        wh = Warehouse(name=name.strip(), code=code_clean, address=address.strip() if address else None, is_active=True)
        db.session.add(wh)
        db.session.flush()

        # Create a default internal location for this warehouse
        loc_code = f"{wh.code}/STOCK"
        loc = Location(
            warehouse_id=wh.id,
            name="Stock Floor",
            code=loc_code,
            location_type="internal",
            is_active=True
        )
        db.session.add(loc)
        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log_event(
            action='WAREHOUSE_CREATED',
            resource_type='warehouse',
            resource_id=str(wh.id),
            details=f"Created warehouse {wh.name} ({wh.code})"
        )
        return wh

    @staticmethod
    def update_warehouse(warehouse_id: int, name: str, address: Optional[str] = None, is_active: bool = True) -> Warehouse:
        wh = db.session.get(Warehouse, warehouse_id)
        if not wh:
            raise ValueError(f"Warehouse ID {warehouse_id} not found.")

        wh.name = name.strip()
        wh.address = address.strip() if address else None
        wh.is_active = is_active
        db.session.commit()

        from app.services.audit_service import AuditService
        AuditService.log_event(
            action='WAREHOUSE_UPDATED',
            resource_type='warehouse',
            resource_id=str(wh.id),
            details=f"Updated warehouse {wh.name} ({wh.code})"
        )
        return wh

    @staticmethod
    def create_location(
        warehouse_id: Optional[int],
        name: str,
        code: str,
        location_type: str = 'internal',
        parent_location_id: Optional[int] = None
    ) -> Location:
        code_clean = code.strip().upper()
        if Location.query.filter_by(code=code_clean).first():
            raise ValueError(f"Location code '{code_clean}' is already in use.")

        if warehouse_id:
            wh = db.session.get(Warehouse, warehouse_id)
            if not wh or not wh.is_active:
                raise ValueError("Cannot assign location to an invalid or inactive warehouse.")

        if parent_location_id:
            parent = db.session.get(Location, parent_location_id)
            if not parent or not parent.is_active:
                raise ValueError("Parent location is invalid or inactive.")

        loc = Location(
            warehouse_id=warehouse_id,
            parent_location_id=parent_location_id,
            name=name.strip(),
            code=code_clean,
            location_type=location_type,
            is_active=True
        )
        db.session.add(loc)
        db.session.commit()
        return loc

    @staticmethod
    def update_location(location_id: int, name: str, is_active: bool = True, parent_location_id: Optional[int] = None) -> Location:
        loc = db.session.get(Location, location_id)
        if not loc:
            raise ValueError(f"Location ID {location_id} not found.")

        if parent_location_id and parent_location_id == location_id:
            raise ValueError("A location cannot be its own parent.")

        loc.name = name.strip()
        loc.is_active = is_active
        loc.parent_location_id = parent_location_id
        db.session.commit()
        return loc

    @staticmethod
    def get_warehouse_stock(warehouse_id: int) -> List[Dict[str, Any]]:
        """Returns all product stock balances across all locations inside a given warehouse."""
        wh = db.session.get(Warehouse, warehouse_id)
        if not wh:
            return []

        quants = StockQuant.query.join(Location).join(Product).filter(
            Location.warehouse_id == warehouse_id,
            Location.location_type == 'internal',
            StockQuant.quantity > 0
        ).order_by(Product.name.asc()).all()

        results = []
        for q in quants:
            results.append({
                'product': q.product,
                'location': q.location,
                'quantity': q.quantity,
                'uom': q.product.uom
            })
        return results

    @staticmethod
    def get_location_stock(location_id: int) -> List[Dict[str, Any]]:
        """Returns all non-zero stock items stored in a specific location."""
        quants = StockQuant.query.join(Product).filter(
            StockQuant.location_id == location_id,
            StockQuant.quantity > 0
        ).order_by(Product.name.asc()).all()

        results = []
        for q in quants:
            results.append({
                'product': q.product,
                'quantity': q.quantity,
                'uom': q.product.uom
            })
        return results
