from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, or_
from app.extensions import db
from app.models.product import Product, ProductCategory, StockQuant
from app.models.warehouse import Warehouse, Location
from app.models.operation import StockPicking
from app.models.ledger import StockLedgerEntry
from app.models.user import User
from app.services.movement_service import MovementAnalysisService
from app.services.demand_service import DemandAnalysisService

class DashboardService:
    @staticmethod
    def get_kpis() -> Dict[str, Any]:
        """Calculates real-time inventory KPIs dynamically without hardcoding."""
        products = Product.query.filter_by(is_active=True).all()
        total_products_count = len(products)
        
        in_stock_count = 0
        low_stock_count = 0
        critical_stock_count = 0
        out_of_stock_count = 0

        for p in products:
            st = p.stock_status
            if st == 'in_stock':
                in_stock_count += 1
            elif st == 'critical':
                critical_stock_count += 1
                low_stock_count += 1
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
            'critical_stock_products': critical_stock_count,
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
                'address': wh.address or 'Standard Logistics Hub',
                'total_quantity': float(total_qty or 0.0),
                'product_count': distinct_products or 0
            })
        return summary

    @staticmethod
    def get_stock_summary_by_category() -> List[Dict[str, Any]]:
        """Calculates total stock and low stock count aggregated per product category."""
        categories = ProductCategory.query.all()
        summary = []
        for cat in categories:
            total_qty = db.session.query(func.coalesce(func.sum(StockQuant.quantity), 0.0))\
                .join(Product, StockQuant.product_id == Product.id)\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Product.category_id == cat.id, Location.location_type == 'internal').scalar()

            products = cat.products.filter_by(is_active=True).all()
            low_stock_count = sum(1 for p in products if p.is_low_stock or p.is_out_of_stock)

            summary.append({
                'category_id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'total_quantity': float(total_qty or 0.0),
                'product_count': len(products),
                'low_stock_count': low_stock_count
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
                    'is_critical': p.is_critical_stock,
                    'is_low_stock': 0 < stock <= p.min_stock_level
                })
        return sorted(alerts, key=lambda x: x['current_stock'])

    @staticmethod
    def filter_dashboard_products(
        warehouse_id: Optional[int] = None,
        location_id: Optional[int] = None,
        category_id: Optional[int] = None,
        stock_status: Optional[str] = None,
        movement_status: Optional[str] = None,
        demand_status: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Multi-dimensional inventory filter matching:
        - Warehouse / Location
        - Category
        - Stock Status (in_stock, low_stock, critical, out_of_stock)
        - Movement Status (Fast Moving, Normal Moving, Slow Moving, No Movement)
        - Demand Status (High Demand, Medium Demand, Low Demand, Insufficient data)
        """
        query = Product.query.filter_by(is_active=True)

        if category_id:
            query = query.filter(Product.category_id == category_id)

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                (Product.name.ilike(term)) | (Product.sku.ilike(term)) | (Product.description.ilike(term))
            )

        products = query.order_by(Product.name.asc()).all()
        results = []

        for p in products:
            # Check location/warehouse filter
            if warehouse_id or location_id:
                quant_q = StockQuant.query.join(Location).filter(
                    StockQuant.product_id == p.id,
                    Location.location_type == 'internal'
                )
                if location_id:
                    quant_q = quant_q.filter(StockQuant.location_id == location_id)
                elif warehouse_id:
                    quant_q = quant_q.filter(Location.warehouse_id == warehouse_id)
                loc_stock = quant_q.with_entities(func.coalesce(func.sum(StockQuant.quantity), 0.0)).scalar() or 0.0
                if loc_stock <= 0 and (stock_status != 'out_of_stock'):
                    continue
                display_stock = float(loc_stock)
            else:
                display_stock = p.total_stock

            # Stock status filter
            st = p.stock_status
            if stock_status and stock_status != 'all':
                if stock_status == 'in_stock' and st != 'in_stock':
                    continue
                elif stock_status == 'low_stock' and (st not in ['low_stock', 'critical']):
                    continue
                elif stock_status == 'critical' and st != 'critical':
                    continue
                elif stock_status == 'out_of_stock' and st != 'out_of_stock':
                    continue

            # Movement analysis
            mov = MovementAnalysisService.get_movement_status(p.id)
            if movement_status and movement_status != 'all':
                if movement_status.lower().replace(' ', '_') not in mov['status'].lower().replace(' ', '_'):
                    continue

            # Demand analysis
            dem = DemandAnalysisService.get_demand_status(p.id)
            if demand_status and demand_status != 'all':
                if demand_status.lower().replace(' ', '_') not in dem['status'].lower().replace(' ', '_'):
                    continue

            results.append({
                'product': p,
                'total_stock': display_stock,
                'stock_status': st,
                'stock_status_display': p.stock_status_display,
                'stock_status_badge': p.stock_status_badge,
                'movement': mov,
                'demand': dem
            })

        return results

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

    @staticmethod
    def get_inventory_analytics() -> Dict[str, Any]:
        """
        Computes aggregated data for interactive charts:
        - Category valuation & distribution
        - Warehouse distribution & capacity
        - Movement velocity distribution
        - Stock health status breakdown
        - Transaction trends (past 14 days)
        - Total inventory valuation
        """
        from datetime import datetime, timedelta, timezone
        
        # 1. Category valuation & quantity
        categories = ProductCategory.query.all()
        cat_labels = []
        cat_quantities = []
        cat_valuations = []
        total_valuation = 0.0
        
        for cat in categories:
            products = cat.products.filter_by(is_active=True).all()
            cat_qty = sum(p.total_stock for p in products)
            # Default unit valuation or estimate based on stock
            price = getattr(cat, 'unit_value', 25.0)
            cat_val = cat_qty * price
            
            cat_labels.append(cat.name)
            cat_quantities.append(round(cat_qty, 2))
            cat_valuations.append(round(cat_val, 2))
            total_valuation += cat_val

        # 2. Warehouse distribution
        warehouses = Warehouse.query.filter_by(is_active=True).all()
        wh_labels = []
        wh_quantities = []
        wh_product_counts = []
        for wh in warehouses:
            total_qty = db.session.query(func.coalesce(func.sum(StockQuant.quantity), 0.0))\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Location.warehouse_id == wh.id, Location.location_type == 'internal').scalar()
            
            distinct_products = db.session.query(func.count(func.distinct(StockQuant.product_id)))\
                .join(Location, StockQuant.location_id == Location.id)\
                .filter(Location.warehouse_id == wh.id, Location.location_type == 'internal', StockQuant.quantity > 0).scalar()
            
            wh_labels.append(f"{wh.code} - {wh.name}")
            wh_quantities.append(round(float(total_qty or 0.0), 2))
            wh_product_counts.append(distinct_products or 0)

        # 3. Stock Health status & Velocity
        products = Product.query.filter_by(is_active=True).all()
        status_counts = {'in_stock': 0, 'low_stock': 0, 'critical': 0, 'out_of_stock': 0}
        velocity_counts = {'Fast Moving': 0, 'Normal Moving': 0, 'Slow Moving': 0, 'No Movement': 0}
        
        for p in products:
            st = p.stock_status
            if st in status_counts:
                status_counts[st] += 1
            mov = MovementAnalysisService.get_movement_status(p.id)
            m_status = mov.get('status', 'No Movement')
            if m_status in velocity_counts:
                velocity_counts[m_status] += 1
            else:
                velocity_counts['No Movement'] += 1

        # 4. 14-day daily transaction trends
        today = datetime.now(timezone.utc).date()
        date_labels = []
        inbound_series = []
        outbound_series = []
        transfer_series = []
        
        for i in range(13, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            date_labels.append(day.strftime('%b %d'))
            
            in_qty = db.session.query(func.coalesce(func.sum(StockLedgerEntry.quantity_change), 0.0))\
                .filter(
                    StockLedgerEntry.timestamp >= day_start,
                    StockLedgerEntry.timestamp <= day_end,
                    StockLedgerEntry.quantity_change > 0
                ).scalar()
                
            out_qty = db.session.query(func.coalesce(func.sum(func.abs(StockLedgerEntry.quantity_change)), 0.0))\
                .filter(
                    StockLedgerEntry.timestamp >= day_start,
                    StockLedgerEntry.timestamp <= day_end,
                    StockLedgerEntry.quantity_change < 0
                ).scalar()
                
            tr_count = db.session.query(func.count(StockLedgerEntry.id))\
                .filter(
                    StockLedgerEntry.timestamp >= day_start,
                    StockLedgerEntry.timestamp <= day_end,
                    StockLedgerEntry.movement_type == 'transfer'
                ).scalar()
                
            inbound_series.append(round(float(in_qty or 0.0), 1))
            outbound_series.append(round(float(out_qty or 0.0), 1))
            transfer_series.append(int(tr_count or 0))

        return {
            'total_valuation': round(total_valuation, 2),
            'categories': {
                'labels': cat_labels,
                'quantities': cat_quantities,
                'valuations': cat_valuations
            },
            'warehouses': {
                'labels': wh_labels,
                'quantities': wh_quantities,
                'product_counts': wh_product_counts
            },
            'health': {
                'labels': ['In Stock', 'Low Stock', 'Critical', 'Out of Stock'],
                'data': [
                    status_counts['in_stock'],
                    status_counts['low_stock'],
                    status_counts['critical'],
                    status_counts['out_of_stock']
                ]
            },
            'velocity': {
                'labels': ['Fast Moving', 'Normal Moving', 'Slow Moving', 'No Movement'],
                'data': [
                    velocity_counts['Fast Moving'],
                    velocity_counts['Normal Moving'],
                    velocity_counts['Slow Moving'],
                    velocity_counts['No Movement']
                ]
            },
            'trends': {
                'labels': date_labels,
                'inbound': inbound_series,
                'outbound': outbound_series,
                'transfers': transfer_series
            }
        }
