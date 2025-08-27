from .celery_app import celery
from services.export_service import ExportService
import logging

logger = logging.getLogger(__name__)

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def export_task(self, reference_id):
    """Background task to process export jobs"""
    try:
        logger.info(f"Starting export task for reference_id: {reference_id}")
        
        export_service = ExportService()
        success = export_service.process_export(reference_id)
        
        if success:
            logger.info(f"Export task completed successfully: {reference_id}")
            return {'status': 'completed', 'reference_id': reference_id}
        else:
            logger.error(f"Export task failed: {reference_id}")
            # Let Celery handle the retry
            raise Exception(f"Export processing failed for {reference_id}")
            
    except Exception as exc:
        logger.error(f"Export task error for {reference_id}: {str(exc)}")
        
        # Check if we've exceeded max retries
        if self.request.retries >= self.max_retries:
            logger.error(f"Export task permanently failed after {self.request.retries} retries: {reference_id}")
            return {'status': 'failed', 'reference_id': reference_id, 'error': str(exc)}
        
        # Retry with exponential backoff
        countdown = min(60 * (2 ** self.request.retries), 300)  # Max 5 minutes
        logger.info(f"Retrying export task in {countdown} seconds: {reference_id}")
        
        raise self.retry(exc=exc, countdown=countdown)

@celery.task
def cleanup_old_exports():
    """Periodic task to clean up old export files and records"""
    try:
        from datetime import datetime, timedelta
        from models import db, Export, ExportStatus
        from services.s3_service import S3Service
        
        # Delete exports older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        old_exports = Export.query.filter(
            Export.created_at < cutoff_date,
            Export.status.in_([ExportStatus.COMPLETED, ExportStatus.FAILED, ExportStatus.SUPERSEDED])
        ).all()
        
        s3_service = S3Service()
        deleted_count = 0
        
        for export in old_exports:
            try:
                # Delete file from S3 if it exists
                if export.file_url:
                    s3_service.delete_file(export.file_url)
                
                # Delete database record
                db.session.delete(export)
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Error deleting old export {export.reference_id}: {str(e)}")
                continue
        
        db.session.commit()
        logger.info(f"Cleanup completed: deleted {deleted_count} old exports")
        
        return {'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        db.session.rollback()
        raise

@celery.task
def health_check():
    """Health check task for monitoring"""
    try:
        from models import db
        
        # Test database connection
        db.session.execute('SELECT 1')
        
        # Test S3 connection
        from services.s3_service import S3Service
        s3_service = S3Service()
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            's3': 'connected'
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }