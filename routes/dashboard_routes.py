from flask import Blueprint, render_template, jsonify, request
from middleware.auth import require_auth
from services.dashboard_service import DashboardService
import logging

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
dashboard_service = DashboardService()

@dashboard_bp.route('/', methods=['GET'])
@require_auth
def dashboard_view():
    """Render the dashboard HTML page"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return jsonify({
            'error': 'Failed to load dashboard',
            'message': str(e)
        }), 500

@dashboard_bp.route('/metrics', methods=['GET'])
@require_auth
def get_metrics():
    """Get dashboard metrics"""
    try:
        metrics = dashboard_service.get_metrics()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({
            'error': 'Failed to get metrics',
            'message': str(e)
        }), 500

@dashboard_bp.route('/exports', methods=['GET'])
@require_auth
def get_exports():
    """Get recent exports for dashboard table"""
    try:
        limit = request.args.get('limit', 50, type=int)
        exports = dashboard_service.get_recent_exports(limit=limit)
        
        return jsonify({
            'exports': exports,
            'total': len(exports)
        })
    except Exception as e:
        logger.error(f"Error getting exports: {e}")
        return jsonify({
            'error': 'Failed to get exports',
            'message': str(e)
        }), 500

@dashboard_bp.route('/health', methods=['GET'])
@require_auth
def get_system_health():
    """Get system health status"""
    try:
        health = dashboard_service.get_system_health()
        return jsonify(health)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({
            'error': 'Failed to get system health',
            'message': str(e)
        }), 500

@dashboard_bp.route('/charts', methods=['GET'])
@require_auth
def get_chart_data():
    """Get data for dashboard charts"""
    try:
        chart_data = dashboard_service.get_chart_data()
        return jsonify(chart_data)
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({
            'error': 'Failed to get chart data',
            'message': str(e)
        }), 500

@dashboard_bp.route('/export/<reference_id>', methods=['GET'])
@require_auth
def get_export_details(reference_id):
    """Get detailed information about a specific export"""
    try:
        export_details = dashboard_service.get_export_details(reference_id)
        
        if not export_details:
            return jsonify({
                'error': 'Export not found',
                'message': f'No export found with reference ID: {reference_id}'
            }), 404
        
        return jsonify(export_details)
    except Exception as e:
        logger.error(f"Error getting export details for {reference_id}: {e}")
        return jsonify({
            'error': 'Failed to get export details',
            'message': str(e)
        }), 500

@dashboard_bp.route('/stats', methods=['GET'])
@require_auth
def get_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    try:
        # Get all data in one call for efficiency
        metrics = dashboard_service.get_metrics()
        health = dashboard_service.get_system_health()
        chart_data = dashboard_service.get_chart_data()
        
        return jsonify({
            'metrics': metrics,
            'health': health,
            'charts': chart_data,
            'timestamp': dashboard_service._get_current_timestamp()
        })
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({
            'error': 'Failed to get dashboard statistics',
            'message': str(e)
        }), 500

@dashboard_bp.route('/search', methods=['GET'])
@require_auth
def search_exports():
    """Search exports by various criteria"""
    try:
        # Get search parameters
        reference_id = request.args.get('reference_id')
        table_name = request.args.get('table_name')
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 50, type=int)
        
        # Perform search
        results = dashboard_service.search_exports(
            reference_id=reference_id,
            table_name=table_name,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return jsonify({
            'exports': results,
            'total': len(results)
        })
    except Exception as e:
        logger.error(f"Error searching exports: {e}")
        return jsonify({
            'error': 'Failed to search exports',
            'message': str(e)
        }), 500

@dashboard_bp.route('/actions/retry/<reference_id>', methods=['POST'])
@require_auth
def retry_export(reference_id):
    """Retry a failed export"""
    try:
        result = dashboard_service.retry_export(reference_id)
        
        if result['success']:
            return jsonify({
                'message': 'Export retry initiated successfully',
                'new_reference_id': result.get('new_reference_id')
            })
        else:
            return jsonify({
                'error': 'Failed to retry export',
                'message': result.get('message', 'Unknown error')
            }), 400
    except Exception as e:
        logger.error(f"Error retrying export {reference_id}: {e}")
        return jsonify({
            'error': 'Failed to retry export',
            'message': str(e)
        }), 500

@dashboard_bp.route('/actions/cancel/<reference_id>', methods=['POST'])
@require_auth
def cancel_export(reference_id):
    """Cancel a pending or processing export"""
    try:
        result = dashboard_service.cancel_export(reference_id)
        
        if result['success']:
            return jsonify({
                'message': 'Export cancelled successfully'
            })
        else:
            return jsonify({
                'error': 'Failed to cancel export',
                'message': result.get('message', 'Unknown error')
            }), 400
    except Exception as e:
        logger.error(f"Error cancelling export {reference_id}: {e}")
        return jsonify({
            'error': 'Failed to cancel export',
            'message': str(e)
        }), 500

@dashboard_bp.route('/system/cleanup', methods=['POST'])
@require_auth
def trigger_cleanup():
    """Manually trigger cleanup of old exports"""
    try:
        result = dashboard_service.trigger_cleanup()
        
        return jsonify({
            'message': 'Cleanup initiated successfully',
            'task_id': result.get('task_id')
        })
    except Exception as e:
        logger.error(f"Error triggering cleanup: {e}")
        return jsonify({
            'error': 'Failed to trigger cleanup',
            'message': str(e)
        }), 500

@dashboard_bp.errorhandler(404)
def dashboard_not_found(error):
    """Handle 404 errors for dashboard routes"""
    return jsonify({
        'error': 'Dashboard endpoint not found',
        'message': 'The requested dashboard endpoint does not exist'
    }), 404

@dashboard_bp.errorhandler(500)
def dashboard_internal_error(error):
    """Handle 500 errors for dashboard routes"""
    logger.error(f"Dashboard internal error: {error}")
    return jsonify({
        'error': 'Internal dashboard error',
        'message': 'An unexpected error occurred in the dashboard'
    }), 500