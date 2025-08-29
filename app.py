from flask import Flask
from config.config import Config
from models import db
from routes.export_routes import export_bp
from routes.dashboard_routes import dashboard_bp
from routes.admin_routes import admin_bp
from middleware.auth import jwt_required
from prometheus_flask_exporter import PrometheusMetrics
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import os

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(app)
    
    # Register blueprints
    app.register_blueprint(export_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Health endpoint
    @app.route('/health')
    def health():
        from services.dashboard_service import DashboardService
        
        try:
            dashboard_service = DashboardService()
            system_health = dashboard_service.get_system_health()
            
            # Determine overall status
            all_healthy = all(
                status == 'healthy' 
                for key, status in system_health.items() 
                if key in ['database', 'redis', 's3', 'celery']
            )
            
            overall_status = 'healthy' if all_healthy else 'unhealthy'
            
            return {
                'status': overall_status,
                'service': 'statement-service',
                'version': '1.0.0',
                'components': system_health,
                'timestamp': dashboard_service._get_current_timestamp()
            }, 200 if all_healthy else 503
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'service': 'statement-service',
                'version': '1.0.0',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }, 503
    
    # Setup logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/statement_service.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Statement Service startup')
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)