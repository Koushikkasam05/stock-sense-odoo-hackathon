from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.operation import StockPicking
from app.models.product import Product, StockQuant
from app.services.adjustment_service import AdjustmentService
from app.services.warehouse_service import WarehouseService

adjustments_bp = Blueprint('adjustments', __name__, url_prefix='/adjustments')

@adjustments_bp.route('/')
@login_required
def index():
    query = StockPicking.query.filter_by(picking_type='adjustment')
    adjustments = query.order_by(StockPicking.created_at.desc()).all()
    return render_template('adjustments/index.html', adjustments=adjustments)


@adjustments_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        location_id = request.form.get('location_id', type=int)
        product_id = request.form.get('product_id', type=int)
        counted_qty_str = request.form.get('counted_quantity')
        reason = request.form.get('reason', '').strip()

        if not location_id or not product_id or counted_qty_str is None:
            flash('Location, Product, and Counted Quantity are required.', 'danger')
            return redirect(url_for('adjustments.create'))

        try:
            counted_quantity = float(counted_qty_str)
            if counted_quantity < 0:
                flash('Counted quantity cannot be negative.', 'danger')
                return redirect(url_for('adjustments.create'))

            picking = AdjustmentService.apply_adjustment(
                location_id=location_id,
                product_id=product_id,
                counted_quantity=counted_quantity,
                reason=reason,
                user_id=current_user.id
            )
            flash(f"Inventory Adjustment '{picking.name}' applied successfully.", 'success')
            return redirect(url_for('adjustments.detail', picking_id=picking.id))
        except Exception as e:
            flash(f"Adjustment failed: {e}", 'danger')

    products = Product.query.filter_by(is_active=True).order_by(Product.name.asc()).all()
    locations = WarehouseService.get_internal_locations()
    return render_template('adjustments/form.html', products=products, locations=locations)


@adjustments_bp.route('/api/get-system-qty')
@login_required
def get_system_qty():
    product_id = request.args.get('product_id', type=int)
    location_id = request.args.get('location_id', type=int)
    if not product_id or not location_id:
        return jsonify({'system_qty': 0.0})

    quant = StockQuant.query.filter_by(product_id=product_id, location_id=location_id).first()
    return jsonify({'system_qty': quant.quantity if quant else 0.0})


@adjustments_bp.route('/<int:picking_id>')
@login_required
def detail(picking_id: int):
    picking = db.session.get(StockPicking, picking_id)
    if not picking or picking.picking_type != 'adjustment':
        flash('Adjustment not found.', 'danger')
        return redirect(url_for('adjustments.index'))

    return render_template('adjustments/detail.html', picking=picking)
