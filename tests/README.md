# Tests for GPT-to-Anki

This directory contains unit and integration tests for the Anki feedback synchronization feature.

## Test Structure

- `unit/` - Unit tests for individual components
  - `test_anki_base.py` - Tests for the AbstractAnkiDeck interface
  - `test_anki_connect.py` - Tests for AnkiConnectDeck implementation using aiohttp
  - `test_anki_models.py` - Tests for AnkiNoteFeedback Pydantic model
  - `test_database_anki_feedback.py` - Tests for anki_feedback database operations
  
- `integration/` - Integration tests
  - `test_anki_sync_integration.py` - Tests for the complete sync flow

## Running Tests

### Install Test Dependencies

First, ensure you have the development dependencies installed:

```bash
pip install -e ".[dev]"
# or with uv:
uv pip install -e ".[dev]"
```

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only  
pytest tests/integration/

# Specific test file
pytest tests/unit/test_anki_connect.py

# Specific test class or function
pytest tests/unit/test_anki_connect.py::TestAnkiConnectDeck::test_post_success
```

### Run with Coverage

```bash
pytest tests/ --cov=src/gpt_to_anki --cov-report=html
```

### Run with Verbose Output

```bash
pytest tests/ -v
```

## Test Requirements

The tests use:
- `pytest` - Test framework
- `pytest-asyncio` - For testing async code
- `aiohttp` - For mocking HTTP requests
- SQLite (in-memory) - For database tests

## Key Test Features

1. **AnkiConnectDeck Tests**: Mock aiohttp responses to test AnkiConnect API interactions without requiring a running Anki instance.

2. **Database Tests**: Use temporary SQLite databases to test persistence operations.

3. **Integration Tests**: Test the complete flow from fetching Anki data to storing in the database.

4. **Async Support**: All async operations are properly tested using pytest-asyncio.