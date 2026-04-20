# Modular Applications with Blueprints

**Source:** https://flask.palletsprojects.com/en/2.3.x/blueprints/
**Fetched:** 2025-06-01

## Why Blueprints?

Blueprints let you organize a Flask application into reusable components. Each blueprint can have its own views, templates, static files, and error handlers.

## Creating a Blueprint

```python
from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/login")
def login():
    return "Login page"

@bp.route("/logout")
def logout():
    return "Logged out"
```

## Registering a Blueprint

```python
from flask import Flask

app = Flask(__name__)
app.register_blueprint(bp)
```

After registration, `/auth/login` and `/auth/logout` are available.

## Blueprint Resources

### Templates

Blueprint templates are looked up in a `templates/` folder relative to the blueprint's import name. Set `template_folder` explicitly:

```python
bp = Blueprint("auth", __name__, template_folder="templates")
```

### Static Files

```python
bp = Blueprint("admin", __name__, static_folder="static", static_url_path="/admin/static")
```

## Blueprint-Level Hooks

Blueprints support the same hooks as the app, but scoped to the blueprint:

```python
@bp.before_request
def require_login():
    if not g.user:
        return redirect(url_for("auth.login"))
```

`before_app_request` registers a hook that runs for ALL requests, not just the blueprint's.

## Nesting Blueprints

Blueprints can be nested by registering one inside another:

```python
parent = Blueprint("parent", __name__, url_prefix="/parent")
child = Blueprint("child", __name__, url_prefix="/child")

parent.register_blueprint(child)
app.register_blueprint(parent)
# /parent/child/... routes are available
```

**Note:** Blueprint nesting was added in Flask 2.0. URL prefixes are concatenated.

## Error Handlers

```python
@bp.app_errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404
```

`@bp.errorhandler(404)` handles errors only within the blueprint's routes. `@bp.app_errorhandler(404)` handles 404 errors application-wide.

## Lazy Loading / Deferred Registration

If you need to defer blueprint registration until the app is created (factory pattern):

```python
def create_app():
    app = Flask(__name__)
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    return app
```
