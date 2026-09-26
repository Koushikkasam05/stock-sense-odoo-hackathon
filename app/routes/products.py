from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.product import Product, ProductCategory, StockQuant
from app.models.warehouse import Warehouse, Location
from app.services.product_service import ProductService
from app.services.warehouse_service import WarehouseService
from app.services.dashboard_service import DashboardService
from app.services.movement_service import MovementAnalysisService
from app.services.demand_service import DemandAnalysisService
from app.utils.decorators import manager_required

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def index():
    category_id = request.args.get('category_id', type=int)
    stock_status = request.args.get('stock_status', 'all')
    search_query = request.args.get('q', '').strip()

    query = Product.query

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if search_query:
        term = f"%{search_query}%"
        query = query.filter(
            (Product.name.ilike(term)) | (Product.sku.ilike(term)) | (Product.description.ilike(term))
        )

    products = query.order_by(Product.name.asc()).all()
    
    # Filter by computed stock status if needed
    if stock_status != 'all':
        filtered = []
        for p in products:
            if stock_status == 'low_stock' and (p.is_low_stock or p.is_critical_stock):
                filtered.append(p)
            elif stock_status == 'critical' and p.is_critical_stock:
                filtered.append(p)
            elif stock_status == 'out_of_stock' and p.is_out_of_stock:
                filtered.append(p)
            elif stock_status == 'in_stock' and p.stock_status == 'in_stock':
                filtered.append(p)
        products = filtered

    # Attach movement & demand analysis to products list
    products_with_analysis = []
    for p in products:
        products_with_analysis.append({
            'product': p,
            'movement': MovementAnalysisService.get_movement_status(p.id),
            'demand': DemandAnalysisService.get_demand_status(p.id)
        })

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    return render_template(
        'products/index.html',
        products=products,
        products_with_analysis=products_with_analysis,
        categories=categories,
        current_filters={
            'category_id': category_id,
            'stock_status': stock_status,
            'q': search_query
        }
    )


@products_bp.route('/export/csv')
@login_required
def export_csv():
    import csv
    import io
    from datetime import datetime
    from flask import Response

    products = Product.query.order_by(Product.name.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU Code', 'Product Name', 'Category', 'Unit of Measure', 'Total On-Hand Stock', 'Min Reorder Threshold', 'Stock Status', 'Active Status'])

    for p in products:
        writer.writerow([
            p.sku,
            p.name,
            p.category.name if p.category else 'Uncategorized',
            p.uom,
            p.total_stock,
            p.min_stock_level,
            p.stock_status_display,
            'Active' if p.is_active else 'Inactive'
        ])

    csv_data = output.getvalue()
    filename = f"stocksense_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
@manager_required
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sku = request.form.get('sku', '').strip()
        category_id = request.form.get('category_id', type=int)
        uom = request.form.get('uom', 'Units').strip()
        min_stock_level = request.form.get('min_stock_level', type=float) or 10.0
        description = request.form.get('description', '').strip()
        initial_stock = request.form.get('initial_stock', type=float) or 0.0
        initial_location_id = request.form.get('initial_location_id', type=int)

        if not name or not sku:
            flash('Product Name and SKU are required.', 'danger')
            return redirect(url_for('products.create'))

        try:
            product = ProductService.create_product(
                name=name,
                sku=sku,
                category_id=category_id,
                uom=uom,
                min_stock_level=min_stock_level,
                description=description,
                initial_stock=initial_stock,
                initial_location_id=initial_location_id,
                user_id=current_user.id
            )
            flash(f"Product '{product.name}' created successfully.", 'success')
            return redirect(url_for('products.detail', product_id=product.id))
        except ValueError as e:
            flash(str(e), 'danger')

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    internal_locations = WarehouseService.get_internal_locations()
    return render_template('products/form.html', categories=categories, locations=internal_locations, product=None)


@products_bp.route('/<int:product_id>')
@login_required
def detail(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.index'))

    # Get location breakdown
    quants = StockQuant.query.join(Location).filter(
        StockQuant.product_id == product.id,
        Location.location_type == 'internal'
    ).all()

    # Calculate warehouse distribution table
    warehouse_distribution = []
    total_qty = 0.0
    total_reserved = 0.0
    total_available = 0.0
    warehouses_present = set()

    for q in quants:
        loc = q.location
        wh = loc.warehouse
        if wh:
            warehouses_present.add(wh.name)
        
        qty = q.quantity
        res = q.reserved_quantity
        avail = q.available_quantity

        total_qty += qty
        total_reserved += res
        total_available += avail

        # Local stock status
        if qty <= 0:
            loc_status = 'Out of Stock'
            loc_badge = 'badge bg-dark text-white'
        elif qty <= (product.min_stock_level * 0.25):
            loc_status = 'Critical'
            loc_badge = 'badge bg-danger text-white'
        elif qty <= product.min_stock_level:
            loc_status = 'Low Stock'
            loc_badge = 'badge bg-warning text-dark'
        else:
            loc_status = 'In Stock'
            loc_badge = 'badge bg-success'

        warehouse_distribution.append({
            'warehouse_name': wh.name if wh else 'Unassigned',
            'warehouse_code': wh.code if wh else 'N/A',
            'location_name': loc.name,
            'location_full': loc.full_name,
            'quantity': qty,
            'reserved': res,
            'available': avail,
            'status': loc_status,
            'badge': loc_badge
        })

    # Movement and Demand Analysis
    movement_info = MovementAnalysisService.get_movement_status(product.id)
    demand_info = DemandAnalysisService.get_demand_status(product.id)

    # Get product's recent ledger history
    ledger_entries = DashboardService.filter_ledger_entries(product_id=product.id, limit=30)

    return render_template(
        'products/detail.html',
        product=product,
        quants=quants,
        warehouse_distribution=warehouse_distribution,
        warehouses_count=len(warehouses_present),
        total_reserved=total_reserved,
        total_available=total_available,
        movement_info=movement_info,
        demand_info=demand_info,
        ledger_entries=ledger_entries
    )


@products_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        uom = request.form.get('uom', 'Units').strip()
        min_stock_level = request.form.get('min_stock_level', type=float) or 10.0
        description = request.form.get('description', '').strip()
        is_active = bool(request.form.get('is_active'))

        if not name:
            flash('Product Name is required.', 'danger')
            return redirect(url_for('products.edit', product_id=product.id))

        try:
            ProductService.update_product(
                product_id=product.id,
                name=name,
                category_id=category_id,
                uom=uom,
                min_stock_level=min_stock_level,
                description=description,
                is_active=is_active
            )
            flash('Product updated successfully.', 'success')
            return redirect(url_for('products.detail', product_id=product.id))
        except ValueError as e:
            flash(str(e), 'danger')

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    return render_template('products/form.html', categories=categories, product=product, locations=[])


@products_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@manager_required
def categories():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Category name is required.', 'danger')
        else:
            try:
                ProductService.get_or_create_category(name, description)
                flash(f"Category '{name}' created/updated.", 'success')
            except Exception as e:
                flash(f"Error creating category: {e}", 'danger')

        return redirect(url_for('products.categories'))

    categories_list = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    return render_template('products/categories.html', categories=categories_list)
