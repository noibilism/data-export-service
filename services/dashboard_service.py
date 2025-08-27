from datetime import datetime, timedelta
from sqlalchemy import func, text
from models.export_model import Export, db
from workers.celery_app import celery
import redis
import boto3
from botocore.exceptions import ClientError
import logging
from config.config import Config

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self):
        self.redis_client = None
        self.s3_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize Redis and S3 clients"""
        try:
            # Initialize Redis client
            self.redis_client = redis.Redis.from_url(Config.CELERY_BROKER_URL)
            
            # Initialize S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
        except Exception as e:
            logger.error(f"Error initializing clients: {e}")
    
    def get_metrics(self):
        """Get dashboard metrics"""
        try:
            # Total exports
            total_exports = db.session.query(func.count(Export.id)).scalar() or 0
            
            # Active jobs (pending + processing)
            active_jobs = db.session.query(func.count(Export.id)).filter(
                Export.status.in_(['pending', 'processing'])
            ).scalar() or 0
            
            # Success rate (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_exports = db.session.query(Export).filter(
                Export.created_at >= yesterday
            ).all()
            
            if recent_exports:
                completed_count = sum(1 for exp in recent_exports if exp.status == 'completed')
                success_rate = round((completed_count / len(recent_exports)) * 100, 1)
            else:
                success_rate = 0
            
            # Average processing time (completed exports in last 24 hours)
            avg_processing_time = self._calculate_avg_processing_time()
            
            return {
                'total_exports': total_exports,
                'active_jobs': active_jobs,
                'success_rate': success_rate,
                'avg_processing_time': avg_processing_time
            }
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {
                'total_exports': 0,
                'active_jobs': 0,
                'success_rate': 0,
                'avg_processing_time': '--'
            }
    
    def _calculate_avg_processing_time(self):
        """Calculate average processing time for completed exports"""
        try:
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            # Get completed exports from last 24 hours with processing times
            completed_exports = db.session.query(Export).filter(
                Export.status == 'completed',
                Export.created_at >= yesterday,
                Export.completed_at.isnot(None)
            ).all()
            
            if not completed_exports:
                return '--'
            
            total_time = sum(
                (exp.completed_at - exp.created_at).total_seconds()
                for exp in completed_exports
            )
            
            avg_seconds = total_time / len(completed_exports)
            avg_minutes = round(avg_seconds / 60, 1)
            
            return f"{avg_minutes}"
        except Exception as e:
            logger.error(f"Error calculating avg processing time: {e}")
            return '--'
    
    def get_recent_exports(self, limit=50):
        """Get recent exports for the dashboard table"""
        try:
            exports = db.session.query(Export).order_by(
                Export.created_at.desc()
            ).limit(limit).all()
            
            return [{
                'reference_id': exp.reference_id,
                'table_name': exp.table_name,
                'start_date': exp.start_date.strftime('%Y-%m-%d'),
                'end_date': exp.end_date.strftime('%Y-%m-%d'),
                'status': exp.status,
                'created_at': exp.created_at.isoformat(),
                'completed_at': exp.completed_at.isoformat() if exp.completed_at else None,
                'error_message': exp.error_message
            } for exp in exports]
        except Exception as e:
            logger.error(f"Error getting recent exports: {e}")
            return []
    
    def get_system_health(self):
        """Check system health status"""
        health = {
            'database': self._check_database_health(),
            'redis': self._check_redis_health(),
            's3': self._check_s3_health(),
            'celery': self._check_celery_health(),
            'queue_size': self._get_queue_size(),
            'failed_tasks': self._get_failed_tasks_count(),
            'worker_uptime': self._get_worker_uptime()
        }
        
        return health
    
    def _check_database_health(self):
        """Check database connectivity"""
        try:
            db.session.execute(text('SELECT 1'))
            return 'healthy'
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return 'error'
    
    def _check_redis_health(self):
        """Check Redis connectivity"""
        try:
            if self.redis_client:
                self.redis_client.ping()
                return 'healthy'
            return 'error'
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return 'error'
    
    def _check_s3_health(self):
        """Check S3 connectivity"""
        try:
            if self.s3_client:
                self.s3_client.head_bucket(Bucket=Config.S3_BUCKET)
                return 'healthy'
            return 'error'
        except ClientError as e:
            logger.error(f"S3 health check failed: {e}")
            return 'error'
        except Exception as e:
            logger.error(f"S3 health check failed: {e}")
            return 'error'
    
    def _check_celery_health(self):
        """Check Celery worker health"""
        try:
            # Get active workers
            inspect = celery.control.inspect()
            active_workers = inspect.active()
            
            if active_workers:
                return 'healthy'
            return 'error'
        except Exception as e:
            logger.error(f"Celery health check failed: {e}")
            return 'error'
    
    def _get_queue_size(self):
        """Get current queue size"""
        try:
            if self.redis_client:
                # Get queue length from Redis
                queue_length = self.redis_client.llen('celery')
                return queue_length
            return 0
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return 0
    
    def _get_failed_tasks_count(self):
        """Get count of failed tasks"""
        try:
            # Count failed exports in last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            failed_count = db.session.query(func.count(Export.id)).filter(
                Export.status == 'failed',
                Export.created_at >= yesterday
            ).scalar() or 0
            
            return failed_count
        except Exception as e:
            logger.error(f"Error getting failed tasks count: {e}")
            return 0
    
    def _get_worker_uptime(self):
        """Get worker uptime information"""
        try:
            inspect = celery.control.inspect()
            stats = inspect.stats()
            
            if stats:
                # Get the first worker's uptime
                worker_name = list(stats.keys())[0]
                uptime_seconds = stats[worker_name].get('rusage', {}).get('utime', 0)
                
                if uptime_seconds > 3600:
                    hours = int(uptime_seconds // 3600)
                    return f"{hours}h"
                elif uptime_seconds > 60:
                    minutes = int(uptime_seconds // 60)
                    return f"{minutes}m"
                else:
                    return f"{int(uptime_seconds)}s"
            
            return '--'
        except Exception as e:
            logger.error(f"Error getting worker uptime: {e}")
            return '--'
    
    def get_chart_data(self):
        """Get data for dashboard charts"""
        try:
            # Activity chart data (last 7 days)
            activity_data = self._get_activity_chart_data()
            
            # Status distribution data
            status_data = self._get_status_distribution_data()
            
            return {
                'activity': activity_data,
                'status_distribution': status_data
            }
        except Exception as e:
            logger.error(f"Error getting chart data: {e}")
            return {
                'activity': {'labels': [], 'data': []},
                'status_distribution': {'completed': 0, 'processing': 0, 'pending': 0, 'failed': 0}
            }
    
    def _get_activity_chart_data(self):
        """Get activity chart data for last 7 days"""
        try:
            labels = []
            data = []
            
            for i in range(6, -1, -1):
                date = datetime.utcnow().date() - timedelta(days=i)
                labels.append(date.strftime('%m/%d'))
                
                # Count exports created on this date
                count = db.session.query(func.count(Export.id)).filter(
                    func.date(Export.created_at) == date
                ).scalar() or 0
                
                data.append(count)
            
            return {
                'labels': labels,
                'data': data
            }
        except Exception as e:
            logger.error(f"Error getting activity chart data: {e}")
            return {'labels': [], 'data': []}
    
    def _get_status_distribution_data(self):
        """Get status distribution data for pie chart"""
        try:
            # Get counts for each status
            status_counts = db.session.query(
                Export.status,
                func.count(Export.id)
            ).group_by(Export.status).all()
            
            distribution = {
                'completed': 0,
                'processing': 0,
                'pending': 0,
                'failed': 0
            }
            
            for status, count in status_counts:
                if status in distribution:
                    distribution[status] = count
            
            return distribution
        except Exception as e:
            logger.error(f"Error getting status distribution data: {e}")
            return {'completed': 0, 'processing': 0, 'pending': 0, 'failed': 0}
    
    def get_export_details(self, reference_id):
        """Get detailed information about a specific export"""
        try:
            export = db.session.query(Export).filter(
                Export.reference_id == reference_id
            ).first()
            
            if not export:
                return None
            
            return {
                'reference_id': export.reference_id,
                'table_name': export.table_name,
                'start_date': export.start_date.strftime('%Y-%m-%d'),
                'end_date': export.end_date.strftime('%Y-%m-%d'),
                'status': export.status,
                'created_at': export.created_at.isoformat(),
                'completed_at': export.completed_at.isoformat() if export.completed_at else None,
                'file_path': export.file_path,
                'file_size': export.file_size,
                'row_count': export.row_count,
                'error_message': export.error_message,
                'reused_from_ref': export.reused_from_ref,
                'dedup_key': export.dedup_key
            }
        except Exception as e:
            logger.error(f"Error getting export details: {e}")
            return None
    
    def _get_current_timestamp(self):
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat()
    
    def search_exports(self, reference_id=None, table_name=None, status=None, 
                      start_date=None, end_date=None, limit=50):
        """Search exports by various criteria"""
        try:
            query = db.session.query(Export)
            
            if reference_id:
                query = query.filter(Export.reference_id.like(f'%{reference_id}%'))
            
            if table_name:
                query = query.filter(Export.table_name == table_name)
            
            if status:
                query = query.filter(Export.status == status)
            
            if start_date:
                query = query.filter(Export.created_at >= start_date)
            
            if end_date:
                query = query.filter(Export.created_at <= end_date)
            
            exports = query.order_by(Export.created_at.desc()).limit(limit).all()
            
            return [{
                'reference_id': exp.reference_id,
                'table_name': exp.table_name,
                'start_date': exp.start_date.strftime('%Y-%m-%d'),
                'end_date': exp.end_date.strftime('%Y-%m-%d'),
                'status': exp.status,
                'created_at': exp.created_at.isoformat(),
                'completed_at': exp.completed_at.isoformat() if exp.completed_at else None,
                'error_message': exp.error_message
            } for exp in exports]
        except Exception as e:
            logger.error(f"Error searching exports: {e}")
            return []
    
    def retry_export(self, reference_id):
        """Retry a failed export"""
        try:
            export = db.session.query(Export).filter(
                Export.reference_id == reference_id
            ).first()
            
            if not export:
                return {'success': False, 'message': 'Export not found'}
            
            if export.status not in ['failed']:
                return {'success': False, 'message': 'Only failed exports can be retried'}
            
            # Reset export status to pending
            export.status = 'pending'
            export.error_message = None
            export.completed_at = None
            db.session.commit()
            
            # Re-queue the export task
            from workers.export_worker import export_task
            export_task.delay(reference_id)
            
            return {'success': True, 'new_reference_id': reference_id}
        except Exception as e:
            logger.error(f"Error retrying export {reference_id}: {e}")
            return {'success': False, 'message': str(e)}
    
    def cancel_export(self, reference_id):
        """Cancel a pending or processing export"""
        try:
            export = db.session.query(Export).filter(
                Export.reference_id == reference_id
            ).first()
            
            if not export:
                return {'success': False, 'message': 'Export not found'}
            
            if export.status not in ['pending', 'processing']:
                return {'success': False, 'message': 'Only pending or processing exports can be cancelled'}
            
            # Update export status to failed with cancellation message
            export.status = 'failed'
            export.error_message = 'Export cancelled by user'
            export.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Try to revoke the Celery task if it's still pending
            try:
                celery.control.revoke(reference_id, terminate=True)
            except Exception as revoke_error:
                logger.warning(f"Could not revoke task {reference_id}: {revoke_error}")
            
            return {'success': True}
        except Exception as e:
            logger.error(f"Error cancelling export {reference_id}: {e}")
            return {'success': False, 'message': str(e)}
    
    def trigger_cleanup(self):
        """Manually trigger cleanup of old exports"""
        try:
            from workers.export_worker import cleanup_old_exports
            task = cleanup_old_exports.delay()
            
            return {'task_id': task.id}
        except Exception as e:
            logger.error(f"Error triggering cleanup: {e}")
            raise
            
            return {
                'reference_id': export.reference_id,
                'table_name': export.table_name,
                'start_date': export.start_date.strftime('%Y-%m-%d'),
                'end_date': export.end_date.strftime('%Y-%m-%d'),
                'status': export.status,
                'created_at': export.created_at.isoformat(),
                'completed_at': export.completed_at.isoformat() if export.completed_at else None,
                'file_path': export.file_path,
                'file_size': export.file_size,
                'row_count': export.row_count,
                'error_message': export.error_message,
                'reused_from_ref': export.reused_from_ref,
                'dedup_key': export.dedup_key
            }
        except Exception as e:
            logger.error(f"Error getting export details: {e}")
            return None