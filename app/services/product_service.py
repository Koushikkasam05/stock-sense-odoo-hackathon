from typing import Optional, List, Dict, Any
from app.extensions import db
from app.models.product import Product, ProductCategory, StockQuant
from app.models.warehouse import Warehouse, Location
from app.services.stock_service import StockService
from app.services.warehouse_service import WarehouseService
from app.services.audit_service import AuditService

class ProductService:
    @staticmethod
    def get_or_create_category(name: str, description: Optional[str] = None) -> ProductCategory:
        name_clean = name.strip()
        cat = ProductCategory.query.filter(ProductCategory.name.ilike(name_clean)).first()
        if not cat:
            cat = ProductCategory(name=name_clean, description=description)
            db.session.add(cat)
            db.session.commit()
            AuditService.log_event(
                action='CATEGORY_CREATED',
                resource_type='category',
                resource_id=str(cat.id),
                details=f"Created category: {cat.name}"
            )
        return cat

    @staticmethod
    def create_product(
        name: str,
        sku: str,
        category_id: Optional[int] = None,
        uom: str = 'Units',
        min_stock_level: float = 10.0,
        description: Optional[str] = None,
        initial_stock: float = 0.0,
        initial_location_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Product:
        sku_clean = sku.strip().upper()
        name_clean = name.strip()

        if Product.query.filter_by(sku=sku_clean).first():
            raise ValueError(f"A product with SKU '{sku_clean}' already exists.")

        product = Product(
            name=name_clean,
            sku=sku_clean,
            category_id=category_id,
            uom=uom.strip() if uom else 'Units',
            min_stock_level=float(min_stock_level or 10.0),
            description=description.strip() if description else None,
            is_active=True
        )
        db.session.add(product)
        db.session.flush()

        # Record Audit Log
        AuditService.log_event(
            action='PRODUCT_CREATED',
            resource_type='product',
            resource_id=str(product.id),
            details=f"Created product {product.name} (SKU: {product.sku})",
            user_id=user_id
        )

        # Handle initial stock safely via StockService with a ledger entry
        if initial_stock > 0:
            if not initial_location_id:
                WarehouseService.ensure_default_locations()
                main_stock_loc = Location.query.filter_by(code='WH-MAIN/STOCK').first()
                initial_location_id = main_stock_loc.id if main_stock_loc else None

            if initial_location_id:
                StockService.record_stock_movement(
                    product_id=product.id,
                    location_id=initial_location_id,
                    qty_delta=float(initial_stock),
                    movement_type='initial_stock',
                    reference_document=f"INIT/{product.sku}",
                    user_id=user_id,
                    notes="Initial stock upon product creation"
                )

        db.session.commit()
        return product

    @staticmethod
    def update_product(
        product_id: int,
        name: str,
        category_id: Optional[int],
        uom: str,
        min_stock_level: float,
        description: Optional[str],
        is_active: bool = True
    ) -> Product:
        product = db.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        old_details = f"name={product.name}, min_stock={product.min_stock_level}, active={product.is_active}"

        product.name = name.strip()
        product.category_id = category_id
        product.uom = uom.strip() if uom else 'Units'
        product.min_stock_level = float(min_stock_level or 10.0)
        product.description = description.strip() if description else None
        product.is_active = is_active

        db.session.commit()

        AuditService.log_event(
            action='PRODUCT_UPDATED',
            resource_type='product',
            resource_id=str(product.id),
            details=f"Updated product {product.name} (SKU: {product.sku}). Old: [{old_details}]"
        )

        return product

    @staticmethod
    def get_products_with_stock() -> List[Dict[str, Any]]:
        """Returns product list with real-time stock balances and status tags."""
        products = Product.query.order_by(Product.name.asc()).all()
        results = []
        for p in products:
            total_stock = p.total_stock
            results.append({
                'product': p,
                'total_stock': total_stock,
                'status': p.stock_status,
                'category_name': p.category.name if p.category else 'Uncategorized'
            })
        return results
