from flask import Blueprint, render_template, request
from flask_login import login_required
from app.services.dashboard_service import DashboardService
from app.services.warehouse_service import WarehouseService
from app.models.product import ProductCategory
from app.models.warehouse import Location

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Fetch real-time KPIs
    kpis = DashboardService.get_kpis()
    
    # Filter parameters
    doc_type = request.args.get('doc_type', 'all')
    status = request.args.get('status', 'all')
    location_id = request.args.get('location_id', type=int)
    search_query = request.args.get('q', '').strip()

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

    # Locations for filter dropdown
    internal_locations = WarehouseService.get_internal_locations()
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    return render_template(
        'dashboard/index.html',
        kpis=kpis,
        operations=operations,
        recent_ledger=recent_ledger,
        alerts=alerts,
        warehouse_summary=warehouse_summary,
        category_summary=category_summary,
        internal_locations=internal_locations,
        categories=categories,
        current_filters={
            'doc_type': doc_type,
            'status': status,
            'location_id': location_id,
            'q': search_query
        }
    )


@dashboard_bp.route('/alerts')
@login_required
def alerts_view():
    alerts = DashboardService.get_low_and_out_of_stock_alerts()
    return render_template('dashboard/alerts.html', alerts=alerts)
