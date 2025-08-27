"""Create exports table migration

This script creates the exports table with all required fields and indexes.
Run this script to set up the database schema.
"""

from sqlalchemy import create_engine, text
from config.config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_exports_table():
    """Create the exports table with all required fields and indexes"""
    
    # Create database engine
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    # SQL to create exports table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS exports (
        id INT AUTO_INCREMENT PRIMARY KEY,
        reference_id VARCHAR(36) NOT NULL UNIQUE,
        table_name VARCHAR(255) NOT NULL,
        date_from DATE NOT NULL,
        date_to DATE NOT NULL,
        dedup_key VARCHAR(64) NOT NULL,
        status ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'SUPERSEDED') NOT NULL DEFAULT 'PENDING',
        file_url TEXT,
        file_size BIGINT,
        row_count BIGINT,
        reused_from_ref VARCHAR(36),
        retry_count INT DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        started_at TIMESTAMP NULL,
        completed_at TIMESTAMP NULL,
        
        INDEX idx_dedup_key_status (dedup_key, status),
        INDEX idx_table_date_range (table_name, date_from, date_to),
        INDEX idx_created_at (created_at),
        INDEX idx_reference_id (reference_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    try:
        with engine.connect() as conn:
            # Create table
            conn.execute(text(create_table_sql))
            conn.commit()
            logger.info("Successfully created exports table")
            
            # Verify table creation
            result = conn.execute(text("SHOW TABLES LIKE 'exports'"))
            if result.fetchone():
                logger.info("Exports table verified successfully")
            else:
                logger.error("Failed to verify exports table creation")
                
    except Exception as e:
        logger.error(f"Error creating exports table: {str(e)}")
        raise

def drop_exports_table():
    """Drop the exports table (use with caution)"""
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS exports"))
            conn.commit()
            logger.info("Successfully dropped exports table")
    except Exception as e:
        logger.error(f"Error dropping exports table: {str(e)}")
        raise

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'drop':
        print("WARNING: This will drop the exports table and all data!")
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            drop_exports_table()
        else:
            print("Operation cancelled")
    else:
        create_exports_table()