from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, or_
from app.extensions import db
from app.models.product import Product, ProductCategory, StockQuant
from app.models.warehouse import Warehouse, Location
from app.models.operation import StockPicking
from app.models.ledger import StockLedgerEntry
from app.models.user import User

class DashboardService:
    @staticmethod
    def get_kpis() -> Dict[str, Any]:
        """Calculates real-time inventory KPIs dynamically without hardcoding."""
        products = Product.query.filter_by(is_active=True).all()
        total_products_count = len(products)
        
        in_stock_count = 0
        low_stock_count = 0
        out_of_stock_count = 0

        for p in products:
            st = p.stock_status
            if st == 'in_stock':
                in_stock_count += 1
            elif st == 'low_stock':
                low_stock_count += 1
            elif st == 'out_of_stock':
                out_of_stock_count += 1

        pending_receipts = StockPicking.query.filter(
            StockPicking.picking_type == 'receipt',
            StockPicking.status.in_(['draft', 'waiting', 'ready'])
        ).count()

        pending_deliveries = StockPicking.query.filter(
            StockPicking.picking_type == 'delivery',
            StockPicking.status.in_(['draft', 'waiting', 'ready'])
        ).count()

        scheduled_transfers = StockPicking.query.filter(
            StockPicking.picking_type == 'transfer',
            StockPicking.status.in_(['draft', 'waiting', 'ready'])
        ).count()

        total_warehouses = Warehouse.query.filter_by(is_active=True).count()

        return {
            'total_products': total_products_count,
            'in_stock_products': in_stock_count,
            'low_stock_products': low_stock_count,
            'out_of_stock_products': out_of_stock_count,
            'pending_receipts': pending_receipts,
            'pending_deliveries': pending_deliveries,
            'scheduled_transfers': scheduled_transfers,
            'total_warehouses': total_warehouses
        }

    @staticmethod
    def get_stock_summary_by_warehouse() -> List[Dict[str, Any]]:
        """Calculates total quantity of stock aggregated per active warehouse."""
        warehouses = Warehouse.query.filter_by(is_active=True).all()
        summary = []
        for wh in warehouses:
            total_qty = db.session.query(func.coalesce(func.sum(StockQuant.quantity), 0.0))\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Location.warehouse_id == wh.id, Location.location_type == 'internal').scalar()
            
            distinct_products = db.session.query(func.count(func.distinct(StockQuant.product_id)))\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Location.warehouse_id == wh.id, Location.location_type == 'internal', StockQuant.quantity > 0).scalar()

            summary.append({
                'warehouse_id': wh.id,
                'name': wh.name,
                'code': wh.code,
                'total_quantity': float(total_qty or 0.0),
                'product_count': distinct_products or 0
            })
        return summary

    @staticmethod
    def get_stock_summary_by_category() -> List[Dict[str, Any]]:
        """Calculates total stock aggregated per product category."""
        categories = ProductCategory.query.all()
        summary = []
        for cat in categories:
            total_qty = db.session.query(func.coalesce(func.sum(StockQuant.quantity), 0.0))\
                .join(Product, StockQuant.product_id == Product.id)\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Product.category_id == cat.id, Location.location_type == 'internal').scalar()

            product_count = cat.products.filter_by(is_active=True).count()

            summary.append({
                'category_id': cat.id,
                'name': cat.name,
                'total_quantity': float(total_qty or 0.0),
                'product_count': product_count
            })
        return summary

    @staticmethod
    def get_low_and_out_of_stock_alerts() -> List[Dict[str, Any]]:
        """Returns list of products currently in low or out-of-stock state for alerts."""
        products = Product.query.filter_by(is_active=True).all()
        alerts = []
        for p in products:
            stock = p.total_stock
            if stock <= p.min_stock_level:
                alerts.append({
                    'id': p.id,
                    'name': p.name,
                    'sku': p.sku,
                    'category': p.category.name if p.category else 'General',
                    'uom': p.uom,
                    'min_stock_level': p.min_stock_level,
                    'current_stock': stock,
                    'is_out_of_stock': stock <= 0,
                    'is_low_stock': 0 < stock <= p.min_stock_level
                })
        return sorted(alerts, key=lambda x: x['current_stock'])

    @staticmethod
    def filter_operations(
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
        location_id: Optional[int] = None,
        search_query: Optional[str] = None,
        limit: int = 50
    ) -> List[StockPicking]:
        query = StockPicking.query

        if doc_type and doc_type != 'all':
            query = query.filter(StockPicking.picking_type == doc_type)

        if status and status != 'all':
            query = query.filter(StockPicking.status == status)

        if location_id:
            query = query.filter(
                or_(
                    StockPicking.source_location_id == location_id,
                    StockPicking.dest_location_id == location_id
                )
            )

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    StockPicking.name.ilike(term),
                    StockPicking.partner_name.ilike(term),
                    StockPicking.notes.ilike(term)
                )
            )

        return query.order_by(StockPicking.created_at.desc()).limit(limit).all()

    @staticmethod
    def filter_ledger_entries_paginated(
        product_id: Optional[int] = None,
        sku: Optional[str] = None,
        warehouse_id: Optional[int] = None,
        location_id: Optional[int] = None,
        movement_type: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 25
    ):
        """Filters immutable stock ledger audit logs with pagination support."""
        query = StockLedgerEntry.query.join(Product).join(Location)

        if product_id:
            query = query.filter(StockLedgerEntry.product_id == product_id)

        if sku:
            query = query.filter(Product.sku.ilike(f"%{sku.strip()}%"))

        if warehouse_id:
            query = query.filter(Location.warehouse_id == warehouse_id)

        if location_id:
            query = query.filter(StockLedgerEntry.location_id == location_id)

        if movement_type and movement_type != 'all':
            query = query.filter(StockLedgerEntry.movement_type == movement_type)

        if user_id:
            query = query.filter(StockLedgerEntry.user_id == user_id)

        if start_date:
            query = query.filter(StockLedgerEntry.timestamp >= start_date)

        if end_date:
            query = query.filter(StockLedgerEntry.timestamp <= end_date)

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    StockLedgerEntry.reference_document.ilike(term),
                    StockLedgerEntry.notes.ilike(term),
                    Product.name.ilike(term),
                    Product.sku.ilike(term)
                )
            )

        return query.order_by(StockLedgerEntry.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def filter_ledger_entries(
        product_id: Optional[int] = None,
        location_id: Optional[int] = None,
        movement_type: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100
    ) -> List[StockLedgerEntry]:
        query = StockLedgerEntry.query

        if product_id:
            query = query.filter(StockLedgerEntry.product_id == product_id)

        if location_id:
            query = query.filter(StockLedgerEntry.location_id == location_id)

        if movement_type and movement_type != 'all':
            query = query.filter(StockLedgerEntry.movement_type == movement_type)

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    StockLedgerEntry.reference_document.ilike(term),
                    StockLedgerEntry.notes.ilike(term)
                )
            )

        return query.order_by(StockLedgerEntry.timestamp.desc()).limit(limit).all()
