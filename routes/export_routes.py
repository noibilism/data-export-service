from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, date
import hashlib
from models import db, Export, ExportStatus
from middleware.api_key_auth import api_key_required, get_current_api_key_info
from services.export_service import ExportService
from services.s3_service import S3Service
from workers.export_worker import export_task
import logging

export_bp = Blueprint('export', __name__)
logger = logging.getLogger(__name__)

@export_bp.route('/export', methods=['POST'])
@api_key_required
def create_export():
    """Create a new export job or return existing one based on deduplication logic"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['table_name', 'date_from', 'date_to']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        table_name = data['table_name']
        date_from_str = data['date_from']
        date_to_str = data['date_to']
        force_refresh = data.get('force_refresh', False)
        
        # Parse dates
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate date range
        if date_from > date_to:
            return jsonify({'error': 'date_from cannot be after date_to'}), 400
        
        # Compute dedup_key
        dedup_string = f"{table_name}|{date_from_str}|{date_to_str}"
        dedup_key = hashlib.sha256(dedup_string.encode()).hexdigest()
        
        # Get API key info for tracking
        api_key_info = get_current_api_key_info()
        user_id = api_key_info['name'] if api_key_info else 'unknown'
        
        logger.info(f"Export request - User: {user_id}, Table: {table_name}, "
                   f"Date range: {date_from} to {date_to}, Dedup key: {dedup_key}, "
                   f"Force refresh: {force_refresh}")
        
        # Deduplication logic
        should_create_new = force_refresh or date_to == date.today()
        
        if not should_create_new:
            # Check for existing completed export
            existing_export = Export.query.filter_by(
                dedup_key=dedup_key,
                status=ExportStatus.COMPLETED
            ).first()
            
            if existing_export:
                # Generate fresh pre-signed URL
                s3_service = S3Service()
                try:
                    presigned_url = s3_service.generate_presigned_url(existing_export.file_url)
                    existing_export.file_url = presigned_url
                    db.session.commit()
                    
                    logger.info(f"Reusing existing export - Reference ID: {existing_export.reference_id}")
                    
                    return jsonify({
                        'reference_id': existing_export.reference_id,
                        'status': existing_export.status.value,
                        'reused': True,
                        'file_url': presigned_url
                    }), 200
                except Exception as e:
                    logger.error(f"Failed to generate presigned URL for existing export: {str(e)}")
                    # Continue to create new export if URL generation fails
        
        # Mark old jobs as superseded if creating a new canonical job
        if should_create_new:
            Export.query.filter_by(dedup_key=dedup_key).filter(
                Export.status.in_([ExportStatus.COMPLETED, ExportStatus.FAILED])
            ).update({'status': ExportStatus.SUPERSEDED})
        
        # Create new export job
        new_export = Export(
            table_name=table_name,
            date_from=date_from,
            date_to=date_to,
            dedup_key=dedup_key,
            status=ExportStatus.PENDING,
            user_id=user_id
        )
        
        db.session.add(new_export)
        db.session.commit()
        
        # Enqueue background task
        export_task.delay(new_export.reference_id)
        
        logger.info(f"Created new export job - Reference ID: {new_export.reference_id}")
        
        return jsonify({
            'reference_id': new_export.reference_id,
            'status': new_export.status.value,
            'reused': False
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating export: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@export_bp.route('/export/<reference_id>', methods=['GET'])
@api_key_required
def get_export_status(reference_id):
    """Get the status of an export job"""
    try:
        export = Export.query.filter_by(reference_id=reference_id).first()
        
        if not export:
            return jsonify({'error': 'Export not found'}), 404
        
        response_data = {
            'reference_id': export.reference_id,
            'status': export.status.value,
            'table_name': export.table_name,
            'date_from': export.date_from.isoformat(),
            'date_to': export.date_to.isoformat(),
            'created_at': export.created_at.isoformat(),
            'updated_at': export.updated_at.isoformat()
        }
        
        if export.status == ExportStatus.COMPLETED:
            # Generate fresh pre-signed URL
            s3_service = S3Service()
            try:
                presigned_url = s3_service.generate_presigned_url(export.file_url)
                response_data['file_url'] = presigned_url
                response_data['file_size'] = export.file_size
                response_data['row_count'] = export.row_count
                response_data['completed_at'] = export.completed_at.isoformat() if export.completed_at else None
            except Exception as e:
                logger.error(f"Failed to generate presigned URL: {str(e)}")
                return jsonify({'error': 'Failed to generate download URL'}), 500
        
        elif export.status == ExportStatus.FAILED:
            response_data['error_message'] = export.error_message
            response_data['retry_count'] = export.retry_count
        
        elif export.status == ExportStatus.IN_PROGRESS:
            response_data['started_at'] = export.started_at.isoformat() if export.started_at else None
        
        logger.info(f"Status check - Reference ID: {reference_id}, Status: {export.status.value}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error getting export status: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500