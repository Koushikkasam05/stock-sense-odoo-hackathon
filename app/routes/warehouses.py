from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.warehouse import Warehouse, Location
from app.models.product import Product, ProductCategory, StockQuant
from app.services.warehouse_service import WarehouseService
from app.services.movement_service import MovementAnalysisService
from app.services.demand_service import DemandAnalysisService
from app.utils.decorators import manager_required

warehouses_bp = Blueprint('warehouses', __name__, url_prefix='/warehouses')

@warehouses_bp.route('/')
@login_required
def index():
    WarehouseService.ensure_default_locations()
    warehouses = Warehouse.query.order_by(Warehouse.code.asc()).all()
    locations = Location.query.order_by(Location.code.asc()).all()
    return render_template('warehouses/index.html', warehouses=warehouses, locations=locations)


@warehouses_bp.route('/new', methods=['POST'])
@login_required
@manager_required
def create_warehouse():
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    address = request.form.get('address', '').strip()

    if not name or not code:
        flash('Warehouse name and code are required.', 'danger')
        return redirect(url_for('warehouses.index'))

    try:
        wh = WarehouseService.create_warehouse(name=name, code=code, address=address)
        flash(f"Warehouse '{wh.name}' created with default stock floor.", 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('warehouses.index'))


@warehouses_bp.route('/<int:warehouse_id>/edit', methods=['POST'])
@login_required
@manager_required
def edit_warehouse(warehouse_id: int):
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    is_active = bool(request.form.get('is_active'))

    if not name:
        flash('Warehouse name cannot be empty.', 'danger')
        return redirect(url_for('warehouses.index'))

    try:
        WarehouseService.update_warehouse(warehouse_id, name=name, address=address, is_active=is_active)
        flash('Warehouse updated successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('warehouses.index'))


@warehouses_bp.route('/<int:warehouse_id>/stock')
@login_required
def warehouse_stock(warehouse_id: int):
    wh = db.session.get(Warehouse, warehouse_id)
    if not wh:
        flash('Warehouse not found.', 'danger')
        return redirect(url_for('warehouses.index'))

    category_id = request.args.get('category_id', type=int)
    search_query = request.args.get('q', '').strip()

    # Query quants inside this warehouse
    quants_query = StockQuant.query.join(Location).join(Product).filter(
        Location.warehouse_id == warehouse_id,
        Location.location_type == 'internal'
    )

    if category_id:
        quants_query = quants_query.filter(Product.category_id == category_id)

    if search_query:
        term = f"%{search_query}%"
        quants_query = quants_query.filter(
            (Product.name.ilike(term)) | (Product.sku.ilike(term))
        )

    quants = quants_query.order_by(Product.name.asc()).all()

    # Warehouse metrics
    total_qty = 0.0
    total_products = len(quants)
    low_stock_count = 0
    out_of_stock_count = 0
    fast_moving_count = 0
    slow_moving_count = 0

    detailed_stock_items = []
    for q in quants:
        p = q.product
        qty = q.quantity
        res = q.reserved_quantity
        avail = q.available_quantity
        total_qty += qty

        # Stock status
        if qty <= 0:
            st_badge = 'badge bg-dark text-white'
            st_display = 'Out of Stock'
            out_of_stock_count += 1
        elif qty <= (p.min_stock_level * 0.25):
            st_badge = 'badge bg-danger text-white'
            st_display = 'Critical'
            low_stock_count += 1
        elif qty <= p.min_stock_level:
            st_badge = 'badge bg-warning text-dark'
            st_display = 'Low Stock'
            low_stock_count += 1
        else:
            st_badge = 'badge bg-success'
            st_display = 'In Stock'

        mov = MovementAnalysisService.get_movement_status(p.id)
        if 'Fast' in mov['status']:
            fast_moving_count += 1
        elif 'Slow' in mov['status'] or 'No' in mov['status']:
            slow_moving_count += 1

        dem = DemandAnalysisService.get_demand_status(p.id)

        detailed_stock_items.append({
            'quant': q,
            'product': p,
            'location': q.location,
            'quantity': qty,
            'reserved': res,
            'available': avail,
            'stock_status': st_display,
            'stock_badge': st_badge,
            'movement': mov,
            'demand': dem,
            'last_updated': q.updated_at
        })

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    summary_metrics = {
        'total_products': total_products,
        'total_quantity': total_qty,
        'low_stock_products': low_stock_count,
        'out_of_stock_products': out_of_stock_count,
        'fast_moving_products': fast_moving_count,
        'slow_moving_products': slow_moving_count
    }

    return render_template(
        'warehouses/warehouse_stock.html',
        warehouse=wh,
        stock_items=detailed_stock_items,
        summary=summary_metrics,
        categories=categories,
        current_filters={'category_id': category_id, 'q': search_query}
    )


@warehouses_bp.route('/locations/new', methods=['POST'])
@login_required
@manager_required
def create_location():
    warehouse_id = request.form.get('warehouse_id', type=int)
    parent_location_id = request.form.get('parent_location_id', type=int)
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    location_type = request.form.get('location_type', 'internal')

    if not name or not code:
        flash('Location name and code are required.', 'danger')
        return redirect(url_for('warehouses.index'))

    try:
        loc = WarehouseService.create_location(
            warehouse_id=warehouse_id,
            name=name,
            code=code,
            location_type=location_type,
            parent_location_id=parent_location_id
        )
        flash(f"Location '{loc.code}' created successfully.", 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('warehouses.index'))


@warehouses_bp.route('/locations/<int:location_id>/edit', methods=['POST'])
@login_required
@manager_required
def edit_location(location_id: int):
    name = request.form.get('name', '').strip()
    parent_location_id = request.form.get('parent_location_id', type=int)
    is_active = bool(request.form.get('is_active'))

    if not name:
        flash('Location name cannot be empty.', 'danger')
        return redirect(url_for('warehouses.index'))

    try:
        WarehouseService.update_location(location_id, name=name, is_active=is_active, parent_location_id=parent_location_id)
        flash('Location updated successfully.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('warehouses.index'))


@warehouses_bp.route('/locations/<int:location_id>/stock')
@login_required
def location_stock(location_id: int):
    loc = db.session.get(Location, location_id)
    if not loc:
        flash('Location not found.', 'danger')
        return redirect(url_for('warehouses.index'))

    stock_items = WarehouseService.get_location_stock(location_id)
    return render_template('warehouses/location_stock.html', location=loc, stock_items=stock_items)
