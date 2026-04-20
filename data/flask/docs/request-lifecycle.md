# Request Lifecycle and Hooks

**Source:** https://flask.palletsprojects.com/en/2.3.x/lifecycle/
**Fetched:** 2025-06-01

## Request Hooks

Flask provides several decorators to register functions that run at different points in the request lifecycle.

### `@app.before_first_request`

Register a function to run before the first request is handled. Useful for one-time initialization:

```python
@app.before_first_request
def init_db():
    db.create_all()
```

This runs only once, no matter how many requests come in. The function runs in the application context.

### `@app.before_request`

Register a function to run before each request:

```python
@app.before_request
def load_user():
    g.user = get_current_user()
```

If `before_request` returns a response, the view function is never called.

### `@app.after_request`

Register a function to run after each request. Receives the response object:

```python
@app.after_request
def add_header(response):
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

### `@app.teardown_request`

Register a function to run at the end of request handling, even if an exception occurred:

```python
@app.teardown_request
def close_db(exception):
    db.session.remove()
```

## Execution Order

1. `before_first_request` (once only)
2. `before_request`
3. The view function
4. `after_request`
5. `teardown_request`

If any `before_request` function returns a response, the remaining `before_request` functions and the view function are skipped, but `after_request` and `teardown_request` still run.

## The Application Context

The application context (`current_app`, `g`) is pushed automatically when a request context is pushed. Use `app.app_context()` to manually push it outside of requests:

```python
with app.app_context():
    db.create_all()
```

## The Request Context

The request context (`request`, `session`) is pushed when Flask starts handling a request and popped after the response is sent.

## Signals

Flask supports Blinker signals for decoupled notifications:

```python
from flask import request_started, request_finished

def log_request(sender, **extra):
    print(f"Request to {request.url}")

request_started.connect(log_request, app)
```

Available signals: `request_started`, `request_finished`, `request_tearing_down`, `got_request_exception`, `template_rendered`.

## Context Locals

Flask uses Werkzeug's `LocalStack` and `LocalProxy` to make `request`, `session`, `g`, and `current_app` available as thread-local proxies. In async mode, these use `contextvars` instead.
