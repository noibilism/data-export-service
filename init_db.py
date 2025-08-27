#!/usr/bin/env python3
"""
Database initialization script for Statement Service
Creates all necessary tables including the new API key table
"""

from app import create_app
from models import db
from models.api_key_model import ApiKey
from models.export_model import Export

def init_database():
    """Initialize the database with all tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        
        # Create all tables
        db.create_all()
        
        print("Database tables created successfully!")
        print("\nTables created:")
        print("- exports (for export job tracking)")
        print("- api_keys (for API key management)")
        
        # Check if any API keys exist
        api_key_count = ApiKey.query.count()
        print(f"\nCurrent API keys in database: {api_key_count}")
        
        if api_key_count == 0:
            print("\nTo create your first API key:")
            print("1. Start the application: python app.py")
            print("2. Open the dashboard: http://localhost:5000/dashboard")
            print("3. Use the 'Create API Key' button in the API Key Management section")

if __name__ == '__main__':
    init_database()