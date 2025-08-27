import os
from datetime import timedelta

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Export Service Database (MySQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://user:password@localhost/export_service'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Transactions Database (MySQL) - Read-only
    TRANSACTIONS_DATABASE_URI = os.environ.get('TRANSACTIONS_DATABASE_URL') or \
        'mysql+pymysql://readonly_user:password@localhost/transactions'
    
    # Celery settings
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    # AWS S3 settings
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION') or 'us-east-1'
    S3_BUCKET = os.environ.get('S3_BUCKET') or 'statement-exports'
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # Export settings
    PRESIGNED_URL_EXPIRATION = 86400  # 24 hours in seconds
    MAX_RETRY_ATTEMPTS = 3
    CHUNK_SIZE = 10000  # Number of rows to process at once
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'