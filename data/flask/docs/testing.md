# Testing Flask Applications

**Source:** https://flask.palletsprojects.com/en/2.3.x/testing/
**Fetched:** 2025-06-01

## Test Client

Flask provides a test client that simulates requests without running a live server:

```python
import pytest
from myapp import create_app

@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
```

## Making Requests

```python
def test_hello(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Hello" in response.data
```

POST with data:

```python
def test_login(client):
    response = client.post("/auth/login", data={
        "username": "test",
        "password": "secret",
    })
    assert response.status_code == 302
```

POST with JSON:

```python
def test_api(client):
    response = client.post("/api/items", json={"name": "widget"})
    assert response.status_code == 201
```

## Test Client Context

The test client manages its own cookie jar and tracks session state. Access the request context after making a request:

```python
def test_with_context(client):
    with client:
        response = client.get("/dashboard")
        assert request.path == "/dashboard"
        assert session["user_id"] == 42
```

**Important:** Inside the `with client:` block, the request and session contexts remain available after the response is returned. Outside the block, accessing `request` or `session` raises a `RuntimeError`.

## CLI Runner

Test Flask CLI commands:

```python
from click.testing import CliRunner

def test_init_db_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["init-db"])
    assert "Initialized" in result.output
```

## Test Configuration

Pass test-specific configuration:

```python
app = create_app({
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "WTF_CSRF_ENABLED": False,
})
```

`TESTING = True` disables error catching during request handling, so you get real exceptions in tests.

## Fixtures and Factory Pattern

The recommended pattern is the application factory:

```python
# conftest.py
import pytest
from myapp import create_app, db

@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://"})
    with app.app_context():
        db.create_all()
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
```

## Coverage

```bash
$ pip install coverage
$ coverage run -m pytest
$ coverage report
$ coverage html
```
