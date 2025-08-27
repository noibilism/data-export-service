from . import db
from datetime import datetime
import uuid
from enum import Enum

class ExportStatus(Enum):
    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SUPERSEDED = 'SUPERSEDED'

class Export(db.Model):
    __tablename__ = 'exports'
    
    id = db.Column(db.Integer, primary_key=True)
    reference_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    table_name = db.Column(db.String(255), nullable=False)
    date_from = db.Column(db.Date, nullable=False)
    date_to = db.Column(db.Date, nullable=False)
    dedup_key = db.Column(db.String(64), nullable=False, index=True)  # SHA256 hash
    status = db.Column(db.Enum(ExportStatus), nullable=False, default=ExportStatus.PENDING)
    file_url = db.Column(db.Text, nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    row_count = db.Column(db.BigInteger, nullable=True)
    reused_from_ref = db.Column(db.String(36), nullable=True)  # Reference to original export if reused
    retry_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_dedup_key_status', 'dedup_key', 'status'),
        db.Index('idx_table_date_range', 'table_name', 'date_from', 'date_to'),
        db.Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Export {self.reference_id}: {self.table_name} {self.date_from}-{self.date_to} [{self.status.value}]>'
    
    def to_dict(self):
        return {
            'reference_id': self.reference_id,
            'table_name': self.table_name,
            'date_from': self.date_from.isoformat(),
            'date_to': self.date_to.isoformat(),
            'status': self.status.value,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'row_count': self.row_count,
            'reused_from_ref': self.reused_from_ref,
            'retry_count': self.retry_count,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }