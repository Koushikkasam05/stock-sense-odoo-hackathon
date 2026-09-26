from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app.models.product import Product, ProductCategory
from app.models.warehouse import Warehouse, Location
from app.services.movement_service import MovementAnalysisService
from app.services.demand_service import DemandAnalysisService

search_bp = Blueprint('search', __name__, url_prefix='/search')

@search_bp.route('/')
@login_required
def index():
    query_str = request.args.get('q', '').strip()
    products = []
    warehouses = []

    if query_str:
        term = f"%{query_str}%"
        # Search Products
        products = Product.query.outerjoin(ProductCategory).filter(
            (Product.name.ilike(term)) |
            (Product.sku.ilike(term)) |
            (Product.description.ilike(term)) |
            (ProductCategory.name.ilike(term))
        ).order_by(Product.name.asc()).limit(20).all()

        # Search Warehouses
        warehouses = Warehouse.query.filter(
            (Warehouse.name.ilike(term)) |
            (Warehouse.code.ilike(term)) |
            (Warehouse.address.ilike(term))
        ).order_by(Warehouse.name.asc()).limit(10).all()

    return render_template(
        'search/results.html',
        query=query_str,
        products=products,
        warehouses=warehouses
    )


@search_bp.route('/api')
@login_required
def api_search():
    """Fast JSON API for global navbar auto-complete dropdown."""
    query_str = request.args.get('q', '').strip()
    if not query_str:
        return jsonify({'products': [], 'warehouses': []})

    term = f"%{query_str}%"

    # Products
    product_matches = Product.query.outerjoin(ProductCategory).filter(
        (Product.name.ilike(term)) |
        (Product.sku.ilike(term)) |
        (ProductCategory.name.ilike(term))
    ).order_by(Product.name.asc()).limit(6).all()

    # Warehouses
    warehouse_matches = Warehouse.query.filter(
        (Warehouse.name.ilike(term)) |
        (Warehouse.code.ilike(term)) |
        (Warehouse.address.ilike(term))
    ).order_by(Warehouse.name.asc()).limit(4).all()

    products_data = []
    for p in product_matches:
        products_data.append({
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'category': p.category.name if p.category else 'Uncategorized',
            'stock': p.total_stock,
            'uom': p.uom,
            'status': p.stock_status,
            'url': f"/products/{p.id}"
        })

    warehouses_data = []
    for w in warehouse_matches:
        warehouses_data.append({
            'id': w.id,
            'name': w.name,
            'code': w.code,
            'address': w.address or 'No address specified',
            'url': f"/warehouses/{w.id}/stock"
        })

    return jsonify({
        'query': query_str,
        'products': products_data,
        'warehouses': warehouses_data,
        'total_found': len(products_data) + len(warehouses_data)
    })
