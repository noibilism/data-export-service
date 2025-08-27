import csv
import tempfile
import os
from datetime import datetime
import logging
from sqlalchemy import create_engine, text
from flask import current_app
from models import db, Export, ExportStatus
from services.s3_service import S3Service

logger = logging.getLogger(__name__)

class ExportService:
    def __init__(self):
        self.s3_service = S3Service()
        # Create read-only connection to transactions database
        self.transactions_engine = create_engine(
            current_app.config['TRANSACTIONS_DATABASE_URI'],
            pool_pre_ping=True,
            pool_recycle=3600
        )
    
    def process_export(self, reference_id):
        """Process an export job - main worker function"""
        export = Export.query.filter_by(reference_id=reference_id).first()
        if not export:
            logger.error(f"Export not found: {reference_id}")
            return False
        
        try:
            # Update status to IN_PROGRESS
            export.status = ExportStatus.IN_PROGRESS
            export.started_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Starting export processing: {reference_id}")
            
            # Generate temporary file for CSV
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
                temp_file_path = temp_file.name
                
                try:
                    # Export data to CSV
                    row_count = self._export_to_csv(
                        export.table_name,
                        export.date_from,
                        export.date_to,
                        temp_file_path
                    )
                    
                    # Get file size
                    file_size = os.path.getsize(temp_file_path)
                    
                    # Generate S3 key
                    s3_key = self.s3_service.generate_s3_key(
                        export.table_name,
                        export.date_from.strftime('%Y-%m-%d'),
                        export.date_to.strftime('%Y-%m-%d'),
                        export.reference_id
                    )
                    
                    # Upload to S3
                    s3_url = self.s3_service.upload_file(temp_file_path, s3_key)
                    
                    # Update export record
                    export.status = ExportStatus.COMPLETED
                    export.file_url = s3_url
                    export.file_size = file_size
                    export.row_count = row_count
                    export.completed_at = datetime.utcnow()
                    export.error_message = None
                    db.session.commit()
                    
                    logger.info(f"Export completed successfully: {reference_id}, "
                              f"Rows: {row_count}, Size: {file_size} bytes")
                    
                    return True
                    
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Export failed: {reference_id}, Error: {error_msg}")
            
            # Update export record with error
            export.status = ExportStatus.FAILED
            export.error_message = error_msg
            export.retry_count += 1
            db.session.commit()
            
            # Check if we should retry
            if export.retry_count < current_app.config['MAX_RETRY_ATTEMPTS']:
                logger.info(f"Scheduling retry for export: {reference_id}, "
                          f"Attempt: {export.retry_count + 1}")
                # Note: Retry logic would be handled by Celery retry mechanism
                return False
            else:
                logger.error(f"Export failed permanently after {export.retry_count} attempts: {reference_id}")
                return False
    
    def _export_to_csv(self, table_name, date_from, date_to, output_file_path):
        """Export data from transactions database to CSV using streaming"""
        logger.info(f"Exporting data from table: {table_name}, "
                   f"Date range: {date_from} to {date_to}")
        
        # Validate table name to prevent SQL injection
        if not self._is_valid_table_name(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        
        row_count = 0
        chunk_size = current_app.config['CHUNK_SIZE']
        
        with self.transactions_engine.connect() as conn:
            # Use server-side cursor for streaming
            query = text(f"""
                SELECT * FROM {table_name} 
                WHERE created_at BETWEEN :date_from AND :date_to
                ORDER BY created_at, id
            """)
            
            # Execute query with streaming
            result = conn.execution_options(stream_results=True).execute(
                query,
                date_from=date_from,
                date_to=date_to
            )
            
            with open(output_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = None
                
                while True:
                    # Fetch chunk of rows
                    rows = result.fetchmany(chunk_size)
                    if not rows:
                        break
                    
                    # Initialize CSV writer with headers from first chunk
                    if writer is None:
                        fieldnames = rows[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                    
                    # Write rows to CSV
                    for row in rows:
                        writer.writerow(dict(row))
                        row_count += 1
                    
                    # Log progress for large exports
                    if row_count % (chunk_size * 10) == 0:
                        logger.info(f"Processed {row_count} rows for export: {table_name}")
        
        logger.info(f"Export completed: {row_count} rows written to {output_file_path}")
        return row_count
    
    def _is_valid_table_name(self, table_name):
        """Validate table name to prevent SQL injection"""
        # Allow only alphanumeric characters and underscores
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name))
    
    def get_export_metrics(self):
        """Get metrics for monitoring"""
        try:
            with db.session.begin():
                # Job creation vs reuse counts
                total_jobs = db.session.query(Export).count()
                completed_jobs = db.session.query(Export).filter_by(status=ExportStatus.COMPLETED).count()
                failed_jobs = db.session.query(Export).filter_by(status=ExportStatus.FAILED).count()
                pending_jobs = db.session.query(Export).filter_by(status=ExportStatus.PENDING).count()
                in_progress_jobs = db.session.query(Export).filter_by(status=ExportStatus.IN_PROGRESS).count()
                
                # Calculate reuse rate (jobs with reused_from_ref)
                reused_jobs = db.session.query(Export).filter(Export.reused_from_ref.isnot(None)).count()
                
                return {
                    'total_jobs': total_jobs,
                    'completed_jobs': completed_jobs,
                    'failed_jobs': failed_jobs,
                    'pending_jobs': pending_jobs,
                    'in_progress_jobs': in_progress_jobs,
                    'reused_jobs': reused_jobs,
                    'failure_rate': failed_jobs / total_jobs if total_jobs > 0 else 0,
                    'reuse_rate': reused_jobs / total_jobs if total_jobs > 0 else 0
                }
        except Exception as e:
            logger.error(f"Error getting export metrics: {str(e)}")
            return {}