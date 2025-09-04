#!/usr/bin/env python3
"""
Test Flask application using SQLite database
For testing the API key authentication system
"""

import os
import tempfile
from flask import Flask
from models import db
from routes.export_routes import export_bp
from routes.dashboard_routes import dashboard_bp
from routes.admin_routes import admin_bp
from prometheus_flask_exporter import PrometheusMetrics
import logging
from logging.handlers import RotatingFileHandler

def create_test_app():
    app = Flask(__name__, template_folder='templates')
    
    # Test configuration using SQLite
    db_path = os.path.join(tempfile.gettempdir(), 'test_statement_service.db')
    app.config.update({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret-key',
        'TESTING': True,
        
        # Mock AWS/S3 settings for testing
        'AWS_ACCESS_KEY_ID': 'test-access-key',
        'AWS_SECRET_ACCESS_KEY': 'test-secret-key',
        'AWS_REGION': 'us-east-1',
        'S3_BUCKET': 'test-bucket',
        
        # Mock Celery settings
        'CELERY_BROKER_URL': 'memory://',
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        
        # JWT settings (legacy)
        'JWT_SECRET_KEY': 'test-jwt-secret',
        
        # Export settings
        'PRESIGNED_URL_EXPIRATION': 86400,
        'MAX_RETRY_ATTEMPTS': 3,
        'CHUNK_SIZE': 1000,
        'LOG_LEVEL': 'DEBUG'
    })
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Prometheus metrics
    metrics = PrometheusMetrics(app)
    
    # Register blueprints
    app.register_blueprint(export_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Setup logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/test_statement_service.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Test Statement Service startup')
    
    return app

if __name__ == '__main__':
    app = create_test_app()
    
    print("\n" + "="*60)
    print("🚀 TEST STATEMENT SERVICE STARTING")
    print("="*60)
    print(f"📊 Dashboard: http://localhost:5002/dashboard")
    print(f"🔑 API Key Management: http://localhost:5002/admin/api-keys")
    print(f"📡 API Endpoints: http://localhost:5002/api/")
    print(f"📈 Metrics: http://localhost:5002/metrics")
    print("\n💡 Test API Key: sk_dbGYC7Gw-CfDa3n1ritzO7sdzNwqJ-0o8iwuJMlhNTI")
    print("\n📝 Example API call:")
    print('curl -H "Authorization: Bearer sk_dbGYC7Gw-CfDa3n1ritzO7sdzNwqJ-0o8iwuJMlhNTI" \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"account_id":"123","table_name":"transactions","date_from":"2024-01-01","date_to":"2024-01-31"}\' \\')
    print('     http://localhost:5002/api/export')
    print("="*60)
    
    app.run(debug=True, host='0.0.0.0', port=5002)