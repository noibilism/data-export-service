from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Text
from models import db
import secrets
import hashlib

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hash of the key
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for display
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    
    def __init__(self, name, description=None):
        self.id = secrets.token_urlsafe(16)
        self.name = name
        self.description = description
        # Generate a secure API key
        raw_key = f"sk_{secrets.token_urlsafe(32)}"
        self.key_prefix = raw_key[:8]
        self.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        self._raw_key = raw_key  # Store temporarily for return
    
    @classmethod
    def verify_key(cls, api_key):
        """Verify an API key and return the ApiKey object if valid"""
        if not api_key or not api_key.startswith('sk_'):
            return None
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        api_key_obj = cls.query.filter_by(key_hash=key_hash, is_active=True).first()
        
        if api_key_obj:
            # Update last_used timestamp
            api_key_obj.last_used = datetime.utcnow()
            db.session.commit()
        
        return api_key_obj
    
    def deactivate(self):
        """Deactivate the API key"""
        self.is_active = False
        db.session.commit()
    
    def activate(self):
        """Activate the API key"""
        self.is_active = True
        db.session.commit()
    
    def to_dict(self, include_key=False):
        """Convert to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'name': self.name,
            'key_prefix': self.key_prefix,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active,
            'description': self.description
        }
        
        if include_key and hasattr(self, '_raw_key'):
            result['key'] = self._raw_key
        
        return result
    
    def __repr__(self):
        return f'<ApiKey {self.name} ({self.key_prefix}...)>'