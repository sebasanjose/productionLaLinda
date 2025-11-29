# Test Implementation Details

## Required Dependencies

Create a `requirements-dev.txt` file with the following content:

```
# Testing dependencies
pytest==7.4.0
pytest-flask==1.2.0
pytest-mock==3.11.1
coverage==7.3.0
```

## Directory Structure

Create the following directory structure:

```
tests/
├── conftest.py
├── unit/
│   ├── __init__.py
│   └── test_routes.py
└── integration/
    ├── __init__.py
    └── test_db.py
```

## Test Configuration (conftest.py)

Here's a sample implementation for `conftest.py`:

```python
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
        init_test_db()
    
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

def init_test_db():
    """Initialize the test database with test data."""
    conn = sqlite3.connect(flask_app.config['DATABASE'])
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

@pytest.fixture
def mock_db(monkeypatch):
    """Fixture to mock database connections and operations."""
    class MockCursor:
        def __init__(self):
            self.executed_queries = []
            self.mock_data = {}
        
        def execute(self, query, params=()):
            self.executed_queries.append((query, params))
            return self
        
        def fetchall(self):
            return self.mock_data.get('fetchall', [])
        
        def fetchone(self):
            return self.mock_data.get('fetchone', None)
    
    class MockConnection:
        def __init__(self):
            self.cursor_obj = MockCursor()
            self.committed = False
            self.closed = False
            self.total_changes = 0
        
        def cursor(self):
            return self.cursor_obj
        
        def execute(self, query, params=()):
            self.cursor_obj.execute(query, params)
            return self.cursor_obj
        
        def commit(self):
            self.committed = True
        
        def close(self):
            self.closed = True
    
    mock_conn = MockConnection()
    
    def mock_get_db_connection():
        return mock_conn
    
    monkeypatch.setattr('app.get_db_connection', mock_get_db_connection)
    
    return mock_conn
```

## Example Unit Test (test_routes.py)

Here's a sample implementation for `tests/unit/test_routes.py`:

```python
def test_dashboard_route(client, mock_db):
    """Test the dashboard route."""
    # Configure mock data
    mock_db.cursor_obj.mock_data['fetchall'] = [
        {'market_name': 'Farmers Market', 'event_date': '2023-01-01', 'cash': 100.0, 
         'total_sold': 10.0, 'total_leftover': 2.0, 'id': 1}
    ]
    
    # Make a request to the dashboard route
    response = client.get('/')
    
    # Assert response is successful
    assert response.status_code == 200
    
    # Check that the correct template is rendered with expected data
    assert b'Dashboard' in response.data
    assert b'Farmers Market' in response.data

def test_inventory_route(client, mock_db):
    """Test the inventory route."""
    # Configure mock data for wrapped inventory
    wrapped_data = [{'name': 'Beef', 'wrapped_unbaked': 5.0}, 
                   {'name': 'Chicken', 'wrapped_unbaked': 3.0}]
    
    # Configure mock data for baked inventory
    baked_data = [{'name': 'Beef', 'available': 10.0}, 
                 {'name': 'Chicken', 'available': 7.0}]
    
    # Configure mock data for tapas totals
    tapas_data = {'total_regular': 20.0, 'total_ghee': 15.0, 'grand_total': 35.0}
    
    # Set up the mock to return different data for different queries
    def mock_fetchall():
        query = mock_db.cursor_obj.executed_queries[-1][0]
        if 'wrapped_unbaked' in query:
            return wrapped_data
        elif 'available' in query:
            return baked_data
        elif 'tapas_production' in query:
            return [tapas_data]
        return []
    
    def mock_fetchone():
        query = mock_db.cursor_obj.executed_queries[-1][0]
        if 'tapas_production' in query:
            return tapas_data
        return None
    
    mock_db.cursor_obj.fetchall = mock_fetchall
    mock_db.cursor_obj.fetchone = mock_fetchone
    
    # Make a request to the inventory route
    response = client.get('/inventory')
    
    # Assert response is successful
    assert response.status_code == 200
    
    # Check that the correct template is rendered with expected data
    assert b'Inventory' in response.data
    assert b'Beef' in response.data
    assert b'Chicken' in response.data
    assert b'5.0' in response.data  # Wrapped inventory for Beef
    assert b'10.0' in response.data  # Baked inventory for Beef
    assert b'20.0' in response.data  # Regular tapas
    assert b'15.0' in response.data  # Ghee tapas

def test_add_flavor_route_get(client):
    """Test the GET request to add_flavor route."""
    response = client.get('/add_flavor')
    
    # Assert response is successful
    assert response.status_code == 200
    
    # Check that the correct template is rendered
    assert b'Add Flavor' in response.data

def test_add_flavor_route_post_success(client, mock_db):
    """Test successful POST request to add_flavor route."""
    # Configure mock
    mock_db.total_changes = 1
    
    # Make a POST request to add a flavor
    response = client.post('/add_flavor', data={'name': 'New Flavor'})
    
    # Assert redirect to production page
    assert response.status_code == 302
    assert response.location.endswith('/production')
    
    # Check that the correct SQL was executed
    executed_query = mock_db.cursor_obj.executed_queries[-1]
    assert 'INSERT INTO flavors' in executed_query[0]
    assert executed_query[1] == ('New Flavor',)
    
    # Check that the transaction was committed
    assert mock_db.committed

def test_add_flavor_route_post_duplicate(client, mock_db, monkeypatch):
    """Test POST request with duplicate flavor name."""
    # Configure mock to raise IntegrityError
    def mock_execute(*args, **kwargs):
        from sqlite3 import IntegrityError
        raise IntegrityError("UNIQUE constraint failed")
    
    monkeypatch.setattr(mock_db, 'execute', mock_execute)
    
    # Make a POST request with a duplicate flavor name
    response = client.post('/add_flavor', data={'name': 'Existing Flavor'})
    
    # Assert response is successful (returns to the form)
    assert response.status_code == 200
    
    # Check that an error message is displayed
    assert b'already exists' in response.data
```

## Example Integration Test (test_db.py)

Here's a sample implementation for `tests/integration/test_db.py`:

```python
import sqlite3
from app import get_db_connection, get_wrapped_inventory, get_fully_baked_inventory

def test_get_db_connection():
    """Test that the database connection is established correctly."""
    conn = get_db_connection()
    
    # Check that the connection is a SQLite connection
    assert isinstance(conn, sqlite3.Connection)
    
    # Check that the row factory is set correctly
    assert conn.row_factory == sqlite3.Row
    
    conn.close()

def test_get_wrapped_inventory(app):
    """Test the get_wrapped_inventory function."""
    with app.app_context():
        conn = get_db_connection()
        
        # Insert test data
        flavor_id = conn.execute("SELECT id FROM flavors WHERE name = 'Beef'").fetchone()['id']
        conn.execute("INSERT INTO empanada_wrapped_added (date, flavor_id, dozens) VALUES ('2023-01-01', ?, 10.0)",
                    (flavor_id,))
        conn.execute("INSERT INTO empanada_baked (date, flavor_id, dozens) VALUES ('2023-01-01', ?, 4.0)",
                    (flavor_id,))
        conn.commit()
        
        # Get wrapped inventory
        inventory = get_wrapped_inventory(conn)
        
        # Check that the inventory is calculated correctly
        assert 'Beef' in inventory
        assert inventory['Beef'] == 6.0  # 10 wrapped - 4 baked = 6 remaining
        
        conn.close()

def test_get_fully_baked_inventory(app):
    """Test the get_fully_baked_inventory function."""
    with app.app_context():
        conn = get_db_connection()
        
        # Insert test data
        flavor_id = conn.execute("SELECT id FROM flavors WHERE name = 'Chicken'").fetchone()['id']
        conn.execute("INSERT INTO empanada_baked (date, flavor_id, dozens) VALUES ('2023-01-01', ?, 8.0)",
                    (flavor_id,))
        
        # Create a market event
        market_id = conn.execute("SELECT id FROM markets WHERE name = 'Farmers Market'").fetchone()['id']
        conn.execute("INSERT INTO market_events (market_id, event_date) VALUES (?, '2023-01-02')",
                    (market_id,))
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Allocate some empanadas to the market event
        conn.execute("""
            INSERT INTO market_flavor_data (market_event_id, flavor_id, allocated, sold, leftover)
            VALUES (?, ?, 5.0, 4.0, 1.0)
        """, (event_id, flavor_id))
        
        conn.commit()
        
        # Get baked inventory
        inventory = get_fully_baked_inventory(conn)
        
        # Check that the inventory is calculated correctly
        assert 'Chicken' in inventory
        assert inventory['Chicken'] == 4.0  # 8 baked - 5 allocated + 1 leftover = 4 available
        
        conn.close()
```

## Running Tests

To run the tests, you would use the following commands:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
coverage run -m pytest
coverage report
coverage html  # Generate HTML report
```

## CI/CD Integration

Create a `.github/workflows/tests.yml` file for GitHub Actions:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest
    
    - name: Run coverage
      run: |
        coverage run -m pytest
        coverage report
        coverage xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml