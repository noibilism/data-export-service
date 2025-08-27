import os

class TestConfig:
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    AWS_ACCESS_KEY_ID = 'test-key'
    AWS_SECRET_ACCESS_KEY = 'test-secret'
    AWS_REGION = 'us-east-1'
    S3_BUCKET = 'test-bucket'
    FLASK_ENV = 'development'
    DEBUG = True
    LOG_LEVEL = 'INFO'