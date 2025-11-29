import pytest
import sqlite3
from app import get_db_connection

def test_get_db_connection():
    """Test that the database connection is established correctly."""
    conn = get_db_connection()
    
    # Check that the connection is a SQLite connection
    assert isinstance(conn, sqlite3.Connection)
    
    # Check that the row factory is set correctly
    assert conn.row_factory == sqlite3.Row
    
    conn.close()