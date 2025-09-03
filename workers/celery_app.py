from celery import Celery
from flask import Flask
from config.config import Config

def make_celery(app):
    """Create Celery instance and configure it with Flask app context"""
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    
    # Update Celery config with Flask config
    celery.conf.update(
        result_backend=app.config['CELERY_RESULT_BACKEND'],
        broker_url=app.config['CELERY_BROKER_URL'],
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,  # 25 minutes
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=False,
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,
        s3_bucket=app.config['S3_BUCKET']
    )
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Create Flask app for Celery worker
def create_celery_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize database
    from models import db
    db.init_app(app)
    
    return app

# Create Celery instance
flask_app = create_celery_app()
celery = make_celery(flask_app)

# Import tasks to register them
from . import export_worker