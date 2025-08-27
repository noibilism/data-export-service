import pytest
import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from app import create_app
from models import db, Export, ExportStatus
from middleware.auth import generate_token

@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['JWT_SECRET_KEY'] = 'test-secret'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def auth_headers(app):
    """Create authorization headers with valid JWT"""
    with app.app_context():
        token = generate_token('test_user_123')
        return {'Authorization': f'Bearer {token}'}

class TestExportRoutes:
    
    def test_create_export_success(self, client, auth_headers):
        """Test successful export creation"""
        with patch('workers.export_worker.export_task.delay') as mock_task:
            response = client.post('/api/export', 
                json={
                    'table_name': 'bank_transactions',
                    'date_from': '2024-01-01',
                    'date_to': '2024-01-31'
                },
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert 'reference_id' in data
            assert data['status'] == 'PENDING'
            assert data['reused'] == False
            mock_task.assert_called_once()
    
    def test_create_export_missing_fields(self, client, auth_headers):
        """Test export creation with missing required fields"""
        response = client.post('/api/export',
            json={
                'table_name': 'bank_transactions'
                # Missing date_from and date_to
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Missing required field' in data['error']
    
    def test_create_export_invalid_date_format(self, client, auth_headers):
        """Test export creation with invalid date format"""
        response = client.post('/api/export',
            json={
                'table_name': 'bank_transactions',
                'date_from': '2024/01/01',  # Invalid format
                'date_to': '2024-01-31'
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid date format' in data['error']
    
    def test_create_export_invalid_date_range(self, client, auth_headers):
        """Test export creation with invalid date range"""
        response = client.post('/api/export',
            json={
                'table_name': 'bank_transactions',
                'date_from': '2024-01-31',
                'date_to': '2024-01-01'  # date_to before date_from
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'date_from cannot be after date_to' in data['error']
    
    def test_create_export_deduplication_reuse(self, client, auth_headers, app):
        """Test export deduplication - reusing existing completed export"""
        with app.app_context():
            # Create existing completed export
            existing_export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_dedup_key',
                status=ExportStatus.COMPLETED,
                file_url='s3://bucket/test.csv'
            )
            db.session.add(existing_export)
            db.session.commit()
            
            with patch('services.s3_service.S3Service.generate_presigned_url') as mock_url:
                mock_url.return_value = 'https://presigned-url.com/test.csv'
                
                response = client.post('/api/export',
                    json={
                        'table_name': 'bank_transactions',
                        'date_from': '2024-01-01',
                        'date_to': '2024-01-31'
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['reused'] == True
                assert data['status'] == 'COMPLETED'
                assert 'file_url' in data
    
    def test_create_export_force_refresh(self, client, auth_headers, app):
        """Test export creation with force_refresh=True"""
        with app.app_context():
            # Create existing completed export
            existing_export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_dedup_key',
                status=ExportStatus.COMPLETED,
                file_url='s3://bucket/test.csv'
            )
            db.session.add(existing_export)
            db.session.commit()
            
            with patch('workers.export_worker.export_task.delay') as mock_task:
                response = client.post('/api/export',
                    json={
                        'table_name': 'bank_transactions',
                        'date_from': '2024-01-01',
                        'date_to': '2024-01-31',
                        'force_refresh': True
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == 201
                data = json.loads(response.data)
                assert data['reused'] == False
                assert data['status'] == 'PENDING'
                mock_task.assert_called_once()
    
    def test_get_export_status_not_found(self, client, auth_headers):
        """Test getting status of non-existent export"""
        response = client.get('/api/export/non-existent-id', headers=auth_headers)
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'Export not found' in data['error']
    
    def test_get_export_status_pending(self, client, auth_headers, app):
        """Test getting status of pending export"""
        with app.app_context():
            export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_dedup_key',
                status=ExportStatus.PENDING
            )
            db.session.add(export)
            db.session.commit()
            
            response = client.get(f'/api/export/{export.reference_id}', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'PENDING'
            assert data['reference_id'] == export.reference_id
            assert 'file_url' not in data
    
    def test_get_export_status_completed(self, client, auth_headers, app):
        """Test getting status of completed export"""
        with app.app_context():
            export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_dedup_key',
                status=ExportStatus.COMPLETED,
                file_url='s3://bucket/test.csv',
                file_size=1024,
                row_count=100,
                completed_at=datetime.utcnow()
            )
            db.session.add(export)
            db.session.commit()
            
            with patch('services.s3_service.S3Service.generate_presigned_url') as mock_url:
                mock_url.return_value = 'https://presigned-url.com/test.csv'
                
                response = client.get(f'/api/export/{export.reference_id}', headers=auth_headers)
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['status'] == 'COMPLETED'
                assert data['file_url'] == 'https://presigned-url.com/test.csv'
                assert data['file_size'] == 1024
                assert data['row_count'] == 100
    
    def test_get_export_status_failed(self, client, auth_headers, app):
        """Test getting status of failed export"""
        with app.app_context():
            export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_dedup_key',
                status=ExportStatus.FAILED,
                error_message='Database connection failed',
                retry_count=2
            )
            db.session.add(export)
            db.session.commit()
            
            response = client.get(f'/api/export/{export.reference_id}', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'FAILED'
            assert data['error_message'] == 'Database connection failed'
            assert data['retry_count'] == 2
    
    def test_unauthorized_access(self, client):
        """Test access without authentication"""
        response = client.post('/api/export',
            json={
                'table_name': 'bank_transactions',
                'date_from': '2024-01-01',
                'date_to': '2024-01-31'
            }
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Token is missing' in data['error']
    
    def test_invalid_token(self, client):
        """Test access with invalid token"""
        response = client.post('/api/export',
            json={
                'table_name': 'bank_transactions',
                'date_from': '2024-01-01',
                'date_to': '2024-01-31'
            },
            headers={'Authorization': 'Bearer invalid-token'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Token is invalid' in data['error']