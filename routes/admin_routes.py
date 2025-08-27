from flask import Blueprint, request, jsonify, render_template
from models import db, ApiKey
from middleware.api_key_auth import admin_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/api-keys', methods=['GET'])
@admin_required
def list_api_keys():
    """List all API keys"""
    try:
        api_keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
        return jsonify({
            'api_keys': [key.to_dict() for key in api_keys]
        })
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        return jsonify({'error': 'Failed to list API keys'}), 500

@admin_bp.route('/api-keys', methods=['POST'])
@admin_required
def create_api_key():
    """Create a new API key"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({'error': 'API key name is required'}), 400
        
        name = data['name'].strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'error': 'API key name cannot be empty'}), 400
        
        # Check if name already exists
        existing_key = ApiKey.query.filter_by(name=name).first()
        if existing_key:
            return jsonify({'error': 'API key with this name already exists'}), 400
        
        # Create new API key
        api_key = ApiKey(name=name, description=description)
        db.session.add(api_key)
        db.session.commit()
        
        logger.info(f"Created new API key: {name}")
        
        # Return the key with the raw key (only time it's shown)
        return jsonify({
            'message': 'API key created successfully',
            'api_key': api_key.to_dict(include_key=True)
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating API key: {str(e)}")
        return jsonify({'error': 'Failed to create API key'}), 500

@admin_bp.route('/api-keys/<key_id>', methods=['PUT'])
@admin_required
def update_api_key(key_id):
    """Update an API key (name, description, or status)"""
    try:
        api_key = ApiKey.query.get(key_id)
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({'error': 'Name cannot be empty'}), 400
            
            # Check if name already exists (excluding current key)
            existing_key = ApiKey.query.filter(
                ApiKey.name == name,
                ApiKey.id != key_id
            ).first()
            if existing_key:
                return jsonify({'error': 'API key with this name already exists'}), 400
            
            api_key.name = name
        
        if 'description' in data:
            api_key.description = data['description'].strip()
        
        if 'is_active' in data:
            api_key.is_active = bool(data['is_active'])
        
        db.session.commit()
        
        logger.info(f"Updated API key: {api_key.name}")
        
        return jsonify({
            'message': 'API key updated successfully',
            'api_key': api_key.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating API key: {str(e)}")
        return jsonify({'error': 'Failed to update API key'}), 500

@admin_bp.route('/api-keys/<key_id>', methods=['DELETE'])
@admin_required
def delete_api_key(key_id):
    """Delete an API key"""
    try:
        api_key = ApiKey.query.get(key_id)
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        key_name = api_key.name
        db.session.delete(api_key)
        db.session.commit()
        
        logger.info(f"Deleted API key: {key_name}")
        
        return jsonify({'message': 'API key deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting API key: {str(e)}")
        return jsonify({'error': 'Failed to delete API key'}), 500

@admin_bp.route('/api-keys/<key_id>/deactivate', methods=['POST'])
@admin_required
def deactivate_api_key(key_id):
    """Deactivate an API key"""
    try:
        api_key = ApiKey.query.get(key_id)
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        api_key.deactivate()
        
        logger.info(f"Deactivated API key: {api_key.name}")
        
        return jsonify({
            'message': 'API key deactivated successfully',
            'api_key': api_key.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error deactivating API key: {str(e)}")
        return jsonify({'error': 'Failed to deactivate API key'}), 500

@admin_bp.route('/api-keys/<key_id>/activate', methods=['POST'])
@admin_required
def activate_api_key(key_id):
    """Activate an API key"""
    try:
        api_key = ApiKey.query.get(key_id)
        if not api_key:
            return jsonify({'error': 'API key not found'}), 404
        
        api_key.activate()
        
        logger.info(f"Activated API key: {api_key.name}")
        
        return jsonify({
            'message': 'API key activated successfully',
            'api_key': api_key.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error activating API key: {str(e)}")
        return jsonify({'error': 'Failed to activate API key'}), 500