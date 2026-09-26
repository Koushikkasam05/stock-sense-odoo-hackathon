import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from app.models.product import Product
from app.models.warehouse import Location, Warehouse
from app.models.user import User
from app.services.dashboard_service import DashboardService

ledger_bp = Blueprint('ledger', __name__, url_prefix='/ledger')

@ledger_bp.route('/')
@login_required
def index():
    product_id = request.args.get('product_id', type=int)
    sku = request.args.get('sku', '').strip()
    warehouse_id = request.args.get('warehouse_id', type=int)
    location_id = request.args.get('location_id', type=int)
    movement_type = request.args.get('movement_type', 'all')
    user_id = request.args.get('user_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    start_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            pass

    end_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    pagination = DashboardService.filter_ledger_entries_paginated(
        product_id=product_id,
        sku=sku,
        warehouse_id=warehouse_id,
        location_id=location_id,
        movement_type=movement_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        page=page,
        per_page=20
    )

    products = Product.query.order_by(Product.name.asc()).all()
    warehouses = Warehouse.query.order_by(Warehouse.name.asc()).all()
    locations = Location.query.order_by(Location.code.asc()).all()
    users = User.query.order_by(User.full_name.asc()).all()

    return render_template(
        'ledger/index.html',
        pagination=pagination,
        entries=pagination.items,
        products=products,
        warehouses=warehouses,
        locations=locations,
        users=users,
        current_filters={
            'product_id': product_id,
            'sku': sku,
            'warehouse_id': warehouse_id,
            'location_id': location_id,
            'movement_type': movement_type,
            'user_id': user_id,
            'start_date': start_date_str or '',
            'end_date': end_date_str or '',
            'q': search_query
        }
    )


@ledger_bp.route('/export/csv')
@login_required
def export_csv():
    product_id = request.args.get('product_id', type=int)
    sku = request.args.get('sku', '').strip()
    warehouse_id = request.args.get('warehouse_id', type=int)
    location_id = request.args.get('location_id', type=int)
    movement_type = request.args.get('movement_type', 'all')
    user_id = request.args.get('user_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    search_query = request.args.get('q', '').strip()

    start_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            pass

    end_date = None
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass

    # Retrieve all matching rows without pagination for complete report
    pagination = DashboardService.filter_ledger_entries_paginated(
        product_id=product_id,
        sku=sku,
        warehouse_id=warehouse_id,
        location_id=location_id,
        movement_type=movement_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        page=1,
        per_page=10000
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp (UTC)', 'Reference Document', 'Movement Type', 'Product SKU', 'Product Name', 'Location', 'Quantity Change', 'Unit', 'Balance After', 'Operator', 'Remarks'])

    for e in pagination.items:
        writer.writerow([
            e.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            e.reference_document,
            e.movement_type,
            e.product.sku,
            e.product.name,
            e.location.full_name,
            e.quantity_change,
            e.product.uom,
            e.balance_after,
            e.user.full_name if e.user else 'System',
            e.notes or ''
        ])

    csv_data = output.getvalue()
    filename = f"stocksense_ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
