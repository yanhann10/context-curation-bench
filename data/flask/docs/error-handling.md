# Error Handling and Custom Error Pages

**Source:** https://flask.palletsprojects.com/en/2.3.x/errorhandling/
**Fetched:** 2025-06-01

## Registering Error Handlers

```python
from flask import render_template
from werkzeug.exceptions import HTTPException

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template("500.html"), 500
```

## Handling All HTTP Exceptions

```python
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return render_template("error.html", error=e), e.code
```

## Custom Exception Classes

```python
class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response
```

## Abort

Use `abort()` to immediately stop a request with an error:

```python
from flask import abort

@app.route("/user/<int:user_id>")
def get_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        abort(404)
    return render_template("user.html", user=user)
```

## Error Logging

Flask logs errors to `app.logger`:

```python
@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"Server Error: {error}")
    return render_template("500.html"), 500
```

Configure logging:

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler("error.log", maxBytes=10000, backupCount=1)
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)
```

## Unhandled Exceptions

In debug mode, unhandled exceptions show the interactive debugger. In production, they return a 500 error page. Always register a 500 handler for production.

## Blueprint Error Handlers

Blueprints can register their own error handlers:

```python
@bp.errorhandler(403)
def forbidden(e):
    return render_template("auth/403.html"), 403
```

Blueprint handlers only catch errors from that blueprint's views. Use `@bp.app_errorhandler` for application-wide handling.
