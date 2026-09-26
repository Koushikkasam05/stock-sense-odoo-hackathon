import os
from flask import Flask, render_template, jsonify
from app.config import Config, config_by_name
from app.extensions import db, migrate, login_manager, mail

def create_app(config_class=None):
    if config_class is None:
        env_name = os.environ.get('FLASK_ENV', 'production' if os.environ.get('RENDER') else 'development')
        config_class = config_by_name.get(env_name, Config)

    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.products import products_bp
    from app.routes.warehouses import warehouses_bp
    from app.routes.receipts import receipts_bp
    from app.routes.deliveries import deliveries_bp
    from app.routes.transfers import transfers_bp
    from app.routes.adjustments import adjustments_bp
    from app.routes.ledger import ledger_bp
    from app.routes.notifications import notifications_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(receipts_bp)
    app.register_blueprint(deliveries_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(adjustments_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(notifications_bp)

    # Health Check Endpoint
    @app.route('/health')
    def health_check():
        db_status = "connected"
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception as ex:
            db_status = f"unhealthy: {str(ex)}"

        is_healthy = (db_status == "connected")
        return jsonify({
            "status": "healthy" if is_healthy else "degraded",
            "database": db_status,
            "version": "1.0.0",
            "service": "StockSense Inventory Management"
        }), 200 if is_healthy else 503

    # Template context processors
    @app.context_processor
    def inject_global_metrics():
        from flask_login import current_user
        if current_user.is_authenticated:
            from app.services.dashboard_service import DashboardService
            from app.services.notification_service import NotificationService
            alerts = DashboardService.get_low_and_out_of_stock_alerts()
            unread_notifs = NotificationService.get_user_notifications(user_id=current_user.id, unread_only=True)
            return {
                'global_alert_count': len(alerts),
                'global_unread_notifications': len(unread_notifs),
                'has_critical_alerts': any(a['is_out_of_stock'] for a in alerts)
            }
        return {'global_alert_count': 0, 'global_unread_notifications': 0, 'has_critical_alerts': False}

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    with app.app_context():
        # Ensure database tables exist and system virtual locations are initialized
        try:
            db.create_all()
            from app.services.warehouse_service import WarehouseService
            WarehouseService.ensure_default_locations()
        except Exception:
            pass

    return app
