from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.operation import StockPicking
from app.models.product import Product
from app.services.delivery_service import DeliveryService
from app.services.warehouse_service import WarehouseService
from app.services.stock_service import InsufficientStockError

deliveries_bp = Blueprint('deliveries', __name__, url_prefix='/deliveries')

@deliveries_bp.route('/')
@login_required
def index():
    status = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()

    query = StockPicking.query.filter_by(picking_type='delivery')

    if status != 'all':
        query = query.filter(StockPicking.status == status)

    if search_query:
        term = f"%{search_query}%"
        query = query.filter((StockPicking.name.ilike(term)) | (StockPicking.partner_name.ilike(term)))

    deliveries = query.order_by(StockPicking.created_at.desc()).all()
    return render_template('deliveries/index.html', deliveries=deliveries, current_status=status, q=search_query)


@deliveries_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        source_location_id = request.form.get('source_location_id', type=int)
        scheduled_date_str = request.form.get('scheduled_date')
        notes = request.form.get('notes', '').strip()

        # Parse dynamic line items from form
        product_ids = request.form.getlist('product_id[]')
        demands = request.form.getlist('demand[]')

        if not source_location_id:
            flash('Source location is required.', 'danger')
            return redirect(url_for('deliveries.create'))

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
            flash('Please add at least one product with a valid quantity.', 'danger')
            return redirect(url_for('deliveries.create'))

        scheduled_date = None
        if scheduled_date_str:
            try:
                scheduled_date = datetime.strptime(scheduled_date_str, '%Y-%m-%d')
            except ValueError:
                pass

        try:
            picking = DeliveryService.create_delivery(
                customer_name=customer_name,
                source_location_id=source_location_id,
                lines=lines,
                scheduled_date=scheduled_date,
                notes=notes,
                user_id=current_user.id
            )
            flash(f"Delivery order '{picking.name}' created successfully.", 'success')
            return redirect(url_for('deliveries.detail', picking_id=picking.id))
        except ValueError as e:
            flash(str(e), 'danger')

    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    locations = WarehouseService.get_internal_locations()
    return render_template('deliveries/form.html', products=products, locations=locations)


@deliveries_bp.route('/<int:picking_id>')
@login_required
def detail(picking_id: int):
    picking = db.session.get(StockPicking, picking_id)
    if not picking or picking.picking_type != 'delivery':
        flash('Delivery order not found.', 'danger')
        return redirect(url_for('deliveries.index'))

    return render_template('deliveries/detail.html', picking=picking)


@deliveries_bp.route('/<int:picking_id>/status', methods=['POST'])
@login_required
def change_status(picking_id: int):
    target_status = request.form.get('target_status')
    try:
        DeliveryService.advance_status(picking_id, target_status, user_id=current_user.id)
        flash(f"Delivery order status updated to '{target_status}'.", 'info')
    except Exception as e:
        flash(str(e), 'danger')

    return redirect(url_for('deliveries.detail', picking_id=picking_id))


@deliveries_bp.route('/<int:picking_id>/validate', methods=['POST'])
@login_required
def validate(picking_id: int):
    picking = db.session.get(StockPicking, picking_id)
    if not picking or picking.picking_type != 'delivery':
        flash('Delivery order not found.', 'danger')
        return redirect(url_for('deliveries.index'))

    quantities_done = {}
    for move in picking.moves:
        form_qty = request.form.get(f'qty_done_{move.id}')
        if form_qty is not None:
            try:
                quantities_done[move.id] = float(form_qty)
            except ValueError:
                pass

    try:
        DeliveryService.validate_delivery(picking_id, user_id=current_user.id, quantities_done=quantities_done if quantities_done else None)
        flash(f"Delivery order '{picking.name}' validated and shipped! Stock updated.", 'success')
    except InsufficientStockError as e:
        flash(f"Stock Error: {e}", 'danger')
    except Exception as e:
        flash(f"Error validating delivery: {e}", 'danger')

    return redirect(url_for('deliveries.detail', picking_id=picking.id))
