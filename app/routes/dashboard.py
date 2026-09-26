from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.dashboard_service import DashboardService
from app.services.warehouse_service import WarehouseService
from app.models.product import ProductCategory
from app.models.warehouse import Warehouse, Location

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Fetch real-time KPIs
    kpis = DashboardService.get_kpis()
    
    # Filter parameters for operations
    doc_type = request.args.get('doc_type', 'all')
    status = request.args.get('status', 'all')
    location_id = request.args.get('location_id', type=int)
    warehouse_id = request.args.get('warehouse_id', type=int)
    category_id = request.args.get('category_id', type=int)
    stock_status = request.args.get('stock_status', 'all')
    movement_status = request.args.get('movement_status', 'all')
    demand_status = request.args.get('demand_status', 'all')
    search_query = request.args.get('q', '').strip()

    # Multi-dimensional inventory products filter
    filtered_products = DashboardService.filter_dashboard_products(
        warehouse_id=warehouse_id,
        location_id=location_id,
        category_id=category_id,
        stock_status=stock_status,
        movement_status=movement_status,
        demand_status=demand_status,
        search_query=search_query
    )

    # Filtered operations list
    operations = DashboardService.filter_operations(
        doc_type=doc_type,
        status=status,
        location_id=location_id,
        search_query=search_query,
        limit=25
    )

    # Filtered ledger entries
    recent_ledger = DashboardService.filter_ledger_entries(limit=10)

    # Stock alerts
    alerts = DashboardService.get_low_and_out_of_stock_alerts()

    # Stock summary by warehouse & category
    warehouse_summary = DashboardService.get_stock_summary_by_warehouse()
    category_summary = DashboardService.get_stock_summary_by_category()

    # Locations and Warehouses for filter dropdowns
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.code.asc()).all()
    internal_locations = WarehouseService.get_internal_locations()
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    # Analytics data for Chart.js
    analytics = DashboardService.get_inventory_analytics()

    return render_template(
        'dashboard/index.html',
        kpis=kpis,
        analytics=analytics,
        filtered_products=filtered_products,
        operations=operations,
        recent_ledger=recent_ledger,
        alerts=alerts,
        warehouse_summary=warehouse_summary,
        category_summary=category_summary,
        warehouses=warehouses,
        internal_locations=internal_locations,
        categories=categories,
        current_filters={
            'doc_type': doc_type,
            'status': status,
            'warehouse_id': warehouse_id,
            'location_id': location_id,
            'category_id': category_id,
            'stock_status': stock_status,
            'movement_status': movement_status,
            'demand_status': demand_status,
            'q': search_query
        }
    )


@dashboard_bp.route('/analytics')
@login_required
def analytics_view():
    """Dedicated Interactive Analytics & Visual Reporting Dashboard."""
    analytics = DashboardService.get_inventory_analytics()
    kpis = DashboardService.get_kpis()
    return render_template('dashboard/analytics.html', analytics=analytics, kpis=kpis)


@dashboard_bp.route('/analytics/api')
@login_required
def analytics_api():
    """JSON API for real-time live chart updates."""
    from flask import jsonify
    analytics = DashboardService.get_inventory_analytics()
    return jsonify({'success': True, 'data': analytics})


@dashboard_bp.route('/alerts')
@login_required
def alerts_view():
    alerts = DashboardService.get_low_and_out_of_stock_alerts()
    return render_template('dashboard/alerts.html', alerts=alerts)

