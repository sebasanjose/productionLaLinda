# How to Run Tests for La Linda Empanada Tracker

This document explains how to run the unit tests for the La Linda Empanada Tracker application.

## Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install -r requirements-dev.txt
```

## Running All Tests

To run all tests:

```bash
python -m pytest
```

## Running Tests with Verbose Output

For more detailed output:

```bash
python -m pytest -v
```

## Running Specific Test Files

To run tests from a specific file:

```bash
python -m pytest tests/unit/test_routes.py -v
```

## Running Specific Test Functions

To run a specific test function:

```bash
python -m pytest tests/unit/test_routes.py::test_dashboard_route -v
```

## Running Tests with Coverage

To run tests with coverage reporting:

```bash
coverage run -m pytest
coverage report
```

For a more detailed HTML coverage report:

```bash
coverage html
```

Then open `htmlcov/index.html` in your browser.

## Understanding Test Failures

When tests fail, pytest provides detailed information about what went wrong:

1. The test function that failed
2. The line where the failure occurred
3. The expected vs. actual values (for assertions)
4. The traceback showing how the code reached the failure point

### Common Failures and Solutions

- **KeyError**: Usually means the mock data structure doesn't match what the application expects. Update the mock data to include the missing keys.
- **AssertionError**: The test expected one value but got another. Check if your mock is correctly configured.
- **ImportError**: A required module couldn't be imported. Make sure all dependencies are installed.

## Fixing the Current Test Failures

The current test failures are primarily due to:

1. Mock data structure not matching the application's expectations
2. Mock database not capturing all SQL queries correctly

To fix these issues:

1. Update the mock data in the test files to match the expected structure
2. Improve the mock database implementation in `conftest.py` to better handle SQL queries

## Next Steps

After fixing the current test failures, consider:

1. Adding more test cases to increase coverage
2. Adding integration tests with a real test database
3. Setting up continuous integration to run tests automatically