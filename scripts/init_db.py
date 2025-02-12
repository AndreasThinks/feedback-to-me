#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import our app modules
sys.path.append(str(Path(__file__).parent.parent))

from models import db, metadata

def init_db():
    """Initialize the database by creating all tables"""
    print("Creating database tables...")
    
    try:
        # Create users table first
        users_table = metadata.tables['users']
        users_table.create(db.engine)
        print("✓ Created users table")

        # Create remaining tables
        remaining_tables = [table for name, table in metadata.tables.items() if name != 'users']
        for table in remaining_tables:
            table.create(db.engine)
            print(f"✓ Created table: {table.name}")
        
        print("✓ All tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {str(e)}")

if __name__ == "__main__":
    # Check if DATABASE_URL is set
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL environment variable is not set")
        sys.exit(1)
        
    if not db_url.startswith("postgresql://"):
        print("Error: This script is intended for PostgreSQL databases only")
        sys.exit(1)
    
    try:
        init_db()
        print("\nDatabase initialization completed successfully!")
    except Exception as e:
        print(f"\nError initializing database: {str(e)}")
        sys.exit(1)
