import os
import tempfile
import pytest
from app import app as flask_app
import sqlite3

@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Create a temporary file to isolate the database for each test
    db_fd, db_path = tempfile.mkstemp()
    
    # Configure the app for testing
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': db_path,
    })
    
    # Create the database and load test data
    with flask_app.app_context():
        init_test_db(db_path)
    
    yield flask_app
    
    # Close and remove the temporary database
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()

def init_test_db(db_path):
    """Initialize the test database with test data."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Create tables
    conn.execute('''
    CREATE TABLE IF NOT EXISTS flavors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS markets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS market_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        cash REAL,
        FOREIGN KEY (market_id) REFERENCES markets (id)
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS market_flavor_data (
        market_event_id INTEGER NOT NULL,
        flavor_id INTEGER NOT NULL,
        allocated REAL,
        brought REAL,
        sold REAL,
        leftover REAL,
        PRIMARY KEY (market_event_id, flavor_id),
        FOREIGN KEY (market_event_id) REFERENCES market_events (id),
        FOREIGN KEY (flavor_id) REFERENCES flavors (id)
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS empanada_wrapped_added (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        flavor_id INTEGER NOT NULL,
        dozens REAL NOT NULL,
        FOREIGN KEY (flavor_id) REFERENCES flavors (id)
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS empanada_baked (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        flavor_id INTEGER NOT NULL,
        dozens REAL NOT NULL,
        FOREIGN KEY (flavor_id) REFERENCES flavors (id)
    )
    ''')
    
    conn.execute('''
    CREATE TABLE IF NOT EXISTS tapas_production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        regular_dozens REAL NOT NULL,
        ghee_dozens REAL NOT NULL
    )
    ''')
    
    # Insert test data
    conn.execute("INSERT INTO flavors (name) VALUES ('Beef')")
    conn.execute("INSERT INTO flavors (name) VALUES ('Chicken')")
    conn.execute("INSERT INTO flavors (name) VALUES ('Vegetable')")
    
    conn.execute("INSERT INTO markets (name) VALUES ('Farmers Market')")
    conn.execute("INSERT INTO markets (name) VALUES ('Food Festival')")
    
    conn.commit()
    conn.close()

class MockRow:
    """A mock class that mimics sqlite3.Row, supporting both index and key access."""
    def __init__(self, data, keys=None):
        if isinstance(data, dict):
            self._keys = list(data.keys())
            self._values = list(data.values())
        else:
            self._values = list(data)
            self._keys = keys or [str(i) for i in range(len(self._values))]
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        try:
            return self._values[self._keys.index(key)]
        except ValueError:
            raise KeyError(key)
    
    def keys(self):
        return self._keys

@pytest.fixture
def mock_db(monkeypatch):
    """Fixture to mock database connections and operations."""
    class MockCursor:
        def __init__(self):
            self.executed_queries = []
            self.mock_data = {}
            self.last_query = None
        
        def execute(self, query, params=()):
            self.executed_queries.append((query, params))
            self.last_query = query
            return self
        
        def fetchall(self):
            # If the query contains specific patterns, return appropriate mock data
            if self.last_query and 'market_events me' in self.last_query and 'event_id' in self.last_query:
                return [{'event_id': 1, 'flavor_name': 'Beef', 'allocated': 5.0}]
            elif self.last_query and 'INSERT INTO' in self.last_query:
                # For insert queries, just return empty list
                return []
            return self.mock_data.get('fetchall', [])
        
        def fetchone(self):
            # If the query is checking for available empanadas
            if self.last_query and 'available' in self.last_query:
                if isinstance(self.mock_data.get('fetchone'), list):
                    # Return a MockRow that supports both [0] and key access
                    return MockRow({'available': self.mock_data.get('fetchone')[0]})
                data = self.mock_data.get('fetchone', {'available': 10.0})
                if isinstance(data, dict):
                    return MockRow(data)
                return data
            # If the query is checking for sales
            elif self.last_query and 'sold IS NOT NULL' in self.last_query:
                return self.mock_data.get('fetchone')
            data = self.mock_data.get('fetchone', None)
            if isinstance(data, dict):
                return MockRow(data)
            return data
    
    class MockConnection:
        def __init__(self):
            self.cursor_obj = MockCursor()
            self.committed = False
            self.closed = False
            self.total_changes = 0
            self.queries = {}
        
        def cursor(self):
            return self.cursor_obj
        
        def execute(self, query, params=()):
            # Store the query for later inspection
            if 'INSERT INTO' in query:
                table_name = query.split('INSERT INTO ')[1].split(' ')[0]
                self.queries[table_name] = (query, params)
                
                # For production route tests
                if 'tapas_production' in query:
                    self.cursor_obj.executed_queries.append(('INSERT INTO tapas_production', params))
                elif 'empanada_wrapped_added' in query:
                    self.cursor_obj.executed_queries.append(('INSERT INTO empanada_wrapped_added', params))
                elif 'empanada_baked' in query:
                    self.cursor_obj.executed_queries.append(('INSERT INTO empanada_baked', params))
            
            self.cursor_obj.execute(query, params)
            return self.cursor_obj
        
        def commit(self):
            self.committed = True
        
        def close(self):
            self.closed = True
        
        def row_factory(self, value):
            # This is just a placeholder to avoid AttributeError
            pass
    
    mock_conn = MockConnection()
    
    def mock_get_db_connection():
        return mock_conn
    
    monkeypatch.setattr('app.get_db_connection', mock_get_db_connection)
    
    return mock_conn

@pytest.fixture
def mock_wrapped_inventory(monkeypatch):
    """Mock the get_wrapped_inventory function."""
    def mock_get_wrapped_inventory(conn):
        return {
            'Beef': 5.0,
            'Chicken': 3.0,
            'Vegetable': 2.0
        }
    
    monkeypatch.setattr('app.get_wrapped_inventory', mock_get_wrapped_inventory)

@pytest.fixture
def mock_baked_inventory(monkeypatch):
    """Mock the get_fully_baked_inventory function."""
    def mock_get_fully_baked_inventory(conn):
        return {
            'Beef': 10.0,
            'Chicken': 7.0,
            'Vegetable': 4.0
        }
    
    monkeypatch.setattr('app.get_fully_baked_inventory', mock_get_fully_baked_inventory)