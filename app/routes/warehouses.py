from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.extensions import db
from app.models.warehouse import Warehouse, Location
from app.services.warehouse_service import WarehouseService
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

    stock_items = WarehouseService.get_warehouse_stock(warehouse_id)
    return render_template('warehouses/warehouse_stock.html', warehouse=wh, stock_items=stock_items)


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
