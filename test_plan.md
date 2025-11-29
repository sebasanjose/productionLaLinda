# Unit Testing Plan for La Linda Empanada Tracker

## Overview

This document outlines the approach for adding unit tests to the La Linda Empanada Tracker Flask application. We'll be using pytest as our testing framework and implementing a hybrid approach with both unit tests (using mocks) and integration tests (using a test database).

## Testing Framework and Tools

- **Primary Framework**: pytest
- **Database Approach**: Hybrid (mocking for unit tests, in-memory SQLite for integration tests)
- **Additional Libraries**:
  - pytest-flask: For Flask-specific testing utilities
  - pytest-mock: For mocking dependencies
  - coverage: For measuring test coverage

## Directory Structure

```
/
├── app.py                  # Main application file
├── tests/                  # Test directory
│   ├── conftest.py         # Test configuration and fixtures
│   ├── unit/               # Unit tests with mocked dependencies
│   │   ├── test_routes.py  # Tests for route handlers
│   │   └── test_forms.py   # Tests for form validation
│   └── integration/        # Integration tests with test database
│       ├── test_db.py      # Database operation tests
│       └── test_api.py     # End-to-end API tests
└── requirements-dev.txt    # Development dependencies including testing tools
```

## Test Categories

### 1. Unit Tests for Route Handlers

These tests will focus on the route handlers in `app.py`, mocking the database connection and any other dependencies. We'll test:

- **Dashboard Route (`/`)**: Test that it renders the correct template with expected data
- **Inventory Route (`/inventory`)**: Verify inventory calculations and template rendering
- **Production Route (`/production`)**: Test form handling and database operations
- **Markets Route (`/markets`)**: Test market event creation and allocation
- **Market Results Route (`/market_results/<event_id>`)**: Test result recording
- **Add Flavor/Market Routes**: Test form validation and database operations

### 2. Integration Tests with Test Database

These tests will use an in-memory SQLite database to test the actual database operations:

- **Database Connection**: Test that the connection is established correctly
- **Database Initialization**: Test that tables are created correctly
- **CRUD Operations**: Test create, read, update, and delete operations
- **Data Integrity**: Test constraints and relationships

### 3. Form Validation and Error Handling Tests

- Test form validation for all forms in the application
- Test error handling for invalid inputs
- Test flash messages for success and error cases

### 4. Authentication and Authorization Tests (if applicable)

- Test login/logout functionality
- Test access control for protected routes

## Test Fixtures

We'll create the following fixtures in `conftest.py`:

1. **Flask Application Fixture**: Creates a test instance of the Flask application
2. **Client Fixture**: Creates a test client for making requests
3. **Database Fixture**: Sets up and tears down a test database
4. **Mock Database Fixture**: Creates mock objects for database operations

## Implementation Approach

1. **Start with Basic Setup**: Create the test directory structure and install dependencies
2. **Create Configuration and Fixtures**: Set up `conftest.py` with necessary fixtures
3. **Implement Route Handler Tests**: Focus on testing the route handlers with mocked database
4. **Add Integration Tests**: Implement tests with a test database
5. **Add Form Validation Tests**: Test form validation and error handling
6. **Measure and Improve Coverage**: Use coverage tools to identify untested code

## Example Test Cases

### Example Unit Test for Dashboard Route

```python
def test_dashboard_route(client, mocker):
    # Mock the database connection and query results
    mock_conn = mocker.patch('app.get_db_connection')
    mock_conn.return_value.execute.return_value.fetchall.return_value = [
        {'market_name': 'Test Market', 'event_date': '2023-01-01', 'cash': 100, 
         'total_sold': 10, 'total_leftover': 2}
    ]
    
    # Mock inventory functions
    mocker.patch('app.get_wrapped_inventory', return_value={'Test Flavor': 5})
    mocker.patch('app.get_fully_baked_inventory', return_value={'Test Flavor': 10})
    
    # Make a request to the dashboard route
    response = client.get('/')
    
    # Assert response is successful
    assert response.status_code == 200
    
    # Assert the correct template is rendered
    assert b'Dashboard' in response.data
    assert b'Test Market' in response.data
    assert b'Test Flavor' in response.data
```

### Example Integration Test for Database Operations

```python
def test_add_flavor(test_db_client):
    # Make a POST request to add a flavor
    response = test_db_client.post('/add_flavor', data={'name': 'Test Flavor'})
    
    # Assert redirect to production page
    assert response.status_code == 302
    assert response.location.endswith('/production')
    
    # Check that the flavor was added to the database
    conn = get_db_connection()
    flavor = conn.execute('SELECT * FROM flavors WHERE name = ?', ('Test Flavor',)).fetchone()
    conn.close()
    
    assert flavor is not None
    assert flavor['name'] == 'Test Flavor'
```

## CI/CD Integration

We'll set up GitHub Actions (or another CI/CD platform) to:

1. Run tests automatically on push and pull requests
2. Generate coverage reports
3. Enforce minimum coverage thresholds

## Documentation

We'll add a section to the README.md file explaining:

1. How to run the tests
2. How to measure coverage
3. Guidelines for writing new tests

## Next Steps

After implementing the basic test suite, we can consider:

1. Property-based testing for more complex logic
2. Performance testing for database operations
3. UI testing for the frontend