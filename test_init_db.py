#!/usr/bin/env python3
"""
Test database initialization script using SQLite
Creates all necessary tables for testing the API key system
"""

import os
import tempfile
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models.api_key_model import ApiKey
from models.export_model import Export

def create_test_app():
    """Create a test Flask app with SQLite database"""
    app = Flask(__name__)
    
    # Use SQLite for testing
    db_path = os.path.join(tempfile.gettempdir(), 'test_statement_service.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    return app

def init_test_database():
    """Initialize the test database with all tables"""
    app = create_test_app()
    
    # Initialize database
    from models import db
    db.init_app(app)
    
    with app.app_context():
        print("Creating test database tables...")
        
        # Create all tables
        db.create_all()
        
        print("Test database tables created successfully!")
        print("\nTables created:")
        print("- exports (for export job tracking)")
        print("- api_keys (for API key management)")
        
        # Create a test API key
        test_key = ApiKey(
            name="Test API Key",
            description="Test key for development"
        )
        
        # Get the raw key before saving (it's stored temporarily)
        raw_key = test_key._raw_key
        
        db.session.add(test_key)
        db.session.commit()
        
        print(f"\nTest API key created:")
        print(f"Name: {test_key.name}")
        print(f"Key: {raw_key}")
        print(f"Prefix: {test_key.key_prefix}")
        
        print(f"\nDatabase file location: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("\nYou can now test the API key authentication system!")
        
        return raw_key

if __name__ == '__main__':
    api_key = init_test_database()
    print(f"\nTo test the API, use this key: {api_key}")