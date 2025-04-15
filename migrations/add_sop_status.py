from app import db
from datetime import datetime
from sqlalchemy import Table, Column, Boolean, DateTime, MetaData

def upgrade():
    # Get the metadata
    metadata = MetaData()
    
    # Get the existing table
    sops = Table('sops', metadata, extend_existing=True)
    
    # Add new columns
    with db.engine.connect() as conn:
        conn.execute(db.text('ALTER TABLE sops ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE'))
        conn.execute(db.text('ALTER TABLE sops ADD COLUMN IF NOT EXISTS discontinued_at TIMESTAMP'))
        conn.execute(db.text('UPDATE sops SET is_active = TRUE WHERE is_active IS NULL'))
        conn.commit()

def downgrade():
    # Get the metadata
    metadata = MetaData()
    
    # Get the existing table
    sops = Table('sops', metadata, extend_existing=True)
    
    # Remove columns if they exist
    with db.engine.connect() as conn:
        conn.execute(db.text('ALTER TABLE sops DROP COLUMN IF EXISTS is_active'))
        conn.execute(db.text('ALTER TABLE sops DROP COLUMN IF EXISTS discontinued_at'))
        conn.commit() 