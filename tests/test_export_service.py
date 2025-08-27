import pytest
import tempfile
import os
import csv
from unittest.mock import patch, MagicMock, mock_open
from datetime import date, datetime
from app import create_app
from models import db, Export, ExportStatus
from services.export_service import ExportService

@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['TRANSACTIONS_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['CHUNK_SIZE'] = 100
    app.config['MAX_RETRY_ATTEMPTS'] = 3
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def export_service(app):
    """Create ExportService instance"""
    with app.app_context():
        return ExportService()

class TestExportService:
    
    def test_is_valid_table_name(self, export_service):
        """Test table name validation"""
        # Valid table names
        assert export_service._is_valid_table_name('bank_transactions') == True
        assert export_service._is_valid_table_name('credit_transactions') == True
        assert export_service._is_valid_table_name('table_123') == True
        assert export_service._is_valid_table_name('_private_table') == True
        
        # Invalid table names
        assert export_service._is_valid_table_name('123_table') == False
        assert export_service._is_valid_table_name('table-name') == False
        assert export_service._is_valid_table_name('table name') == False
        assert export_service._is_valid_table_name('table;DROP TABLE') == False
        assert export_service._is_valid_table_name('') == False
    
    @patch('services.export_service.ExportService._export_to_csv')
    @patch('services.s3_service.S3Service.upload_file')
    @patch('services.s3_service.S3Service.generate_s3_key')
    def test_process_export_success(self, mock_s3_key, mock_upload, mock_export_csv, export_service, app):
        """Test successful export processing"""
        with app.app_context():
            # Create test export
            export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_key',
                status=ExportStatus.PENDING
            )
            db.session.add(export)
            db.session.commit()
            
            # Mock return values
            mock_export_csv.return_value = 1000  # row count
            mock_s3_key.return_value = 'exports/bank_transactions/2024-01-01_2024-01-31/test.csv'
            mock_upload.return_value = 's3://bucket/test.csv'
            
            # Mock file size
            with patch('os.path.getsize', return_value=2048):
                result = export_service.process_export(export.reference_id)
            
            assert result == True
            
            # Refresh export from database
            db.session.refresh(export)
            assert export.status == ExportStatus.COMPLETED
            assert export.file_url == 's3://bucket/test.csv'
            assert export.file_size == 2048
            assert export.row_count == 1000
            assert export.completed_at is not None
    
    def test_process_export_not_found(self, export_service, app):
        """Test processing non-existent export"""
        with app.app_context():
            result = export_service.process_export('non-existent-id')
            assert result == False
    
    @patch('services.export_service.ExportService._export_to_csv')
    def test_process_export_failure(self, mock_export_csv, export_service, app):
        """Test export processing failure"""
        with app.app_context():
            # Create test export
            export = Export(
                table_name='bank_transactions',
                date_from=date(2024, 1, 1),
                date_to=date(2024, 1, 31),
                dedup_key='test_key',
                status=ExportStatus.PENDING
            )
            db.session.add(export)
            db.session.commit()
            
            # Mock exception
            mock_export_csv.side_effect = Exception('Database connection failed')
            
            result = export_service.process_export(export.reference_id)
            
            assert result == False
            
            # Refresh export from database
            db.session.refresh(export)
            assert export.status == ExportStatus.FAILED
            assert export.error_message == 'Database connection failed'
            assert export.retry_count == 1
    
    def test_export_to_csv_invalid_table(self, export_service, app):
        """Test CSV export with invalid table name"""
        with app.app_context():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            try:
                with pytest.raises(ValueError, match='Invalid table name'):
                    export_service._export_to_csv(
                        'invalid-table-name',
                        date(2024, 1, 1),
                        date(2024, 1, 31),
                        temp_file_path
                    )
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
    
    @patch('sqlalchemy.create_engine')
    def test_export_to_csv_success(self, mock_engine, export_service, app):
        """Test successful CSV export"""
        with app.app_context():
            # Mock database connection and results
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
            
            # Mock query results
            mock_row1 = MagicMock()
            mock_row1.keys.return_value = ['id', 'amount', 'description']
            mock_row1.__iter__ = lambda self: iter([('id', 1), ('amount', 100.0), ('description', 'Test')])
            
            mock_row2 = MagicMock()
            mock_row2.__iter__ = lambda self: iter([('id', 2), ('amount', 200.0), ('description', 'Test2')])
            
            mock_result = MagicMock()
            mock_result.fetchmany.side_effect = [[mock_row1, mock_row2], []]  # First call returns data, second returns empty
            mock_conn.execution_options.return_value.execute.return_value = mock_result
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
                temp_file_path = temp_file.name
            
            try:
                row_count = export_service._export_to_csv(
                    'bank_transactions',
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    temp_file_path
                )
                
                assert row_count == 2
                
                # Verify CSV content
                with open(temp_file_path, 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    assert len(rows) == 3  # Header + 2 data rows
                    assert rows[0] == ['id', 'amount', 'description']
                    
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
    
    def test_get_export_metrics(self, export_service, app):
        """Test export metrics calculation"""
        with app.app_context():
            # Create test exports
            exports = [
                Export(table_name='test', date_from=date(2024, 1, 1), date_to=date(2024, 1, 31), 
                      dedup_key='key1', status=ExportStatus.COMPLETED),
                Export(table_name='test', date_from=date(2024, 1, 1), date_to=date(2024, 1, 31), 
                      dedup_key='key2', status=ExportStatus.FAILED),
                Export(table_name='test', date_from=date(2024, 1, 1), date_to=date(2024, 1, 31), 
                      dedup_key='key3', status=ExportStatus.PENDING),
                Export(table_name='test', date_from=date(2024, 1, 1), date_to=date(2024, 1, 31), 
                      dedup_key='key4', status=ExportStatus.COMPLETED, reused_from_ref='ref1')
            ]
            
            for export in exports:
                db.session.add(export)
            db.session.commit()
            
            metrics = export_service.get_export_metrics()
            
            assert metrics['total_jobs'] == 4
            assert metrics['completed_jobs'] == 2
            assert metrics['failed_jobs'] == 1
            assert metrics['pending_jobs'] == 1
            assert metrics['reused_jobs'] == 1
            assert metrics['failure_rate'] == 0.25  # 1/4
            assert metrics['reuse_rate'] == 0.25  # 1/4
    
    def test_get_export_metrics_empty(self, export_service, app):
        """Test export metrics with no data"""
        with app.app_context():
            metrics = export_service.get_export_metrics()
            
            assert metrics['total_jobs'] == 0
            assert metrics['completed_jobs'] == 0
            assert metrics['failed_jobs'] == 0
            assert metrics['pending_jobs'] == 0
            assert metrics['reused_jobs'] == 0
            assert metrics['failure_rate'] == 0
            assert metrics['reuse_rate'] == 0