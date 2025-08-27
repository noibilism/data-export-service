from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import random

app = Flask(__name__, template_folder='templates')

# Mock data for testing
def get_mock_metrics():
    return {
        'total_exports': random.randint(100, 500),
        'active_jobs': random.randint(0, 10),
        'success_rate': round(random.uniform(85, 99), 1),
        'avg_processing_time': round(random.uniform(30, 180), 1)
    }

def get_mock_recent_exports():
    statuses = ['COMPLETED', 'FAILED', 'IN_PROGRESS', 'PENDING']
    exports = []
    for i in range(10):
        exports.append({
            'reference_id': f'exp-{random.randint(1000, 9999)}',
            'table_name': random.choice(['bank_transactions', 'credit_transactions']),
            'status': random.choice(statuses),
            'created_at': (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat(),
            'file_size': random.randint(1000, 50000) if random.choice([True, False]) else None
        })
    return exports

def get_mock_system_health():
    return {
        'database': random.choice(['healthy', 'unhealthy']),
        'redis': random.choice(['healthy', 'unhealthy']),
        's3': random.choice(['healthy', 'unhealthy']),
        'celery': random.choice(['healthy', 'unhealthy']),
        'queue_size': random.randint(0, 20),
        'failed_tasks': random.randint(0, 5),
        'worker_uptime': f'{random.randint(1, 72)}h {random.randint(0, 59)}m'
    }

def get_mock_chart_data():
    dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    return {
        'export_activity': {
            'dates': dates,
            'counts': [random.randint(5, 25) for _ in dates]
        },
        'status_distribution': {
            'COMPLETED': random.randint(70, 90),
            'FAILED': random.randint(5, 15),
            'IN_PROGRESS': random.randint(2, 8),
            'PENDING': random.randint(1, 5)
        }
    }

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/dashboard/metrics')
def api_metrics():
    return jsonify(get_mock_metrics())

@app.route('/api/dashboard/recent-exports')
def api_recent_exports():
    return jsonify(get_mock_recent_exports())

@app.route('/api/dashboard/system-health')
def api_system_health():
    return jsonify(get_mock_system_health())

@app.route('/api/dashboard/chart-data')
def api_chart_data():
    return jsonify(get_mock_chart_data())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)