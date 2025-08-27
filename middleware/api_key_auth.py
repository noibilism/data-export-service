from functools import wraps
from flask import request, jsonify, g
from models import ApiKey
import logging

logger = logging.getLogger(__name__)

def api_key_required(f):
    """Decorator for API key authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = None
        
        # Check for API key in different locations
        # 1. Authorization header (Bearer token)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                api_key = auth_header.split(' ')[1]
            elif auth_header.startswith('ApiKey '):
                api_key = auth_header.split(' ')[1]
        
        # 2. X-API-Key header
        if not api_key and 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        
        # 3. Query parameter (less secure, for testing)
        if not api_key and 'api_key' in request.args:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({
                'error': 'API key is required',
                'message': 'Provide API key in Authorization header (Bearer <key>), X-API-Key header, or api_key query parameter'
            }), 401
        
        # Verify the API key
        api_key_obj = ApiKey.verify_key(api_key)
        
        if not api_key_obj:
            logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
            return jsonify({
                'error': 'Invalid or inactive API key',
                'message': 'The provided API key is invalid or has been deactivated'
            }), 401
        
        # Store API key info in Flask's g object for use in the route
        g.api_key = api_key_obj
        g.api_key_id = api_key_obj.id
        g.api_key_name = api_key_obj.name
        
        logger.info(f"API request authenticated with key: {api_key_obj.name} ({api_key_obj.key_prefix}...)")
        
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator for admin-only endpoints (no authentication required for dashboard)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # For now, admin endpoints are open (dashboard access)
        # In production, you might want to add basic auth or IP restrictions
        return f(*args, **kwargs)
    
    return decorated

def get_current_api_key():
    """Get the current API key object from Flask's g"""
    return getattr(g, 'api_key', None)

def get_current_api_key_info():
    """Get current API key information"""
    api_key = get_current_api_key()
    if api_key:
        return {
            'id': api_key.id,
            'name': api_key.name,
            'key_prefix': api_key.key_prefix
        }
    return None