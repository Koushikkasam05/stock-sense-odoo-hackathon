from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.operation import StockPicking
from app.models.product import Product
from app.services.transfer_service import TransferService
from app.services.warehouse_service import WarehouseService
from app.services.stock_service import InsufficientStockError

transfers_bp = Blueprint('transfers', __name__, url_prefix='/transfers')

@transfers_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()

    query = StockPicking.query.filter_by(picking_type='transfer')

    if status != 'all':
        query = query.filter(StockPicking.status == status)

    if search_query:
        term = f"%{search_query}%"
        query = query.filter(StockPicking.name.ilike(term))

    transfers = query.order_by(StockPicking.created_at.desc()).all()
    return render_template('transfers/index.html', transfers=transfers, current_status=status, q=search_query)


@transfers_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        source_location_id = request.form.get('source_location_id', type=int)
        dest_location_id = request.form.get('dest_location_id', type=int)
        scheduled_date_str = request.form.get('scheduled_date')
        notes = request.form.get('notes', '').strip()

        product_ids = request.form.getlist('product_id[]')
        demands = request.form.getlist('demand[]')

        if not source_location_id or not dest_location_id:
            flash('Source and Destination locations are required.', 'danger')
            return redirect(url_for('transfers.create'))

        if source_location_id == dest_location_id:
            flash('Source and destination locations cannot be identical.', 'danger')
            return redirect(url_for('transfers.create'))

        lines = []
        for pid, demand_str in zip(product_ids, demands):
            if pid and demand_str:
                try:
                    demand_val = float(demand_str)
                    if demand_val > 0:
                        lines.append({'product_id': int(pid), 'demand': demand_val})
                except ValueError:
                    continue

        if not lines:
            flash('Please select at least one product with a valid quantity.', 'danger')
            return redirect(url_for('transfers.create'))

        scheduled_date = None
        if scheduled_date_str:
            try:
                scheduled_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d')
            except ValueError:
                pass

        try:
            picking = TransferService.create_transfer(
                source_location_id=source_location_id,
                dest_location_id=dest_location_id,
                lines=lines,
                scheduled_date=scheduled_date,
                notes=notes,
                user_id=current_user.id
            )
            flash(f"Transfer '{picking.name}' scheduled successfully.", 'success')
            return redirect(url_for('transfers.detail', picking_id=picking.id))
        except ValueError as e:
            flash(str(e), 'danger')

    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    locations = WarehouseService.get_internal_locations()
    return render_template('transfers/form.html', products=products, locations=locations)


@transfers_bp.route('/<int:picking_id>')
@login_required
def detail(picking_id: int):
    picking = db.session.get(StockPicking, picking_id)
    if not picking or picking.picking_type != 'transfer':
        flash('Transfer not found.', 'danger')
        return redirect(url_for('transfers.index'))

    return render_template('transfers/detail.html', picking=picking)


@transfers_bp.route('/<int:picking_id>/validate', methods=['POST'])
@login_required
def validate(picking_id: int):
    picking = db.session.get(StockPicking, picking_id)
    if not picking or picking.picking_type != 'transfer':
        flash('Transfer not found.', 'danger')
        return redirect(url_for('transfers.index'))

    quantities_done = {}
    for move in picking.moves:
        form_qty = request.form.get(f'qty_done_{move.id}')
        if form_qty is not None:
            try:
                quantities_done[move.id] = float(form_qty)
            except ValueError:
                pass

    try:
        TransferService.validate_transfer(picking_id, user_id=current_user.id, quantities_done=quantities_done if quantities_done else None)
        flash(f"Transfer '{picking.name}' completed! Stock moved between locations.", 'success')
    except InsufficientStockError as e:
        flash(f"Stock Error: {e}", 'danger')
    except Exception as e:
        flash(f"Error executing transfer: {e}", 'danger')

    return redirect(url_for('transfers.detail', picking_id=picking.id))
