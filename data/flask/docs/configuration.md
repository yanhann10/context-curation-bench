# Configuration Handling

**Source:** https://flask.palletsprojects.com/en/2.3.x/config/
**Fetched:** 2025-06-01

## Configuration Basics

Flask's config is a subclass of `dict`, accessible as `app.config`:

```python
app = Flask(__name__)
app.config["DEBUG"] = True
app.config["SECRET_KEY"] = "dev-key"
```

## Loading from Files

```python
# From Python file
app.config.from_pyfile("config.py")

# From object
app.config.from_object("config.ProductionConfig")

# From JSON file
app.config.from_json("config.json")

# From TOML file (Flask 2.2+)
app.config.from_file("config.toml", load=tomllib.load, text=False)
```

## Environment Variables

Load a config file path from an environment variable:

```python
app.config.from_envvar("APP_SETTINGS")
# reads the file path from os.environ["APP_SETTINGS"]
# then loads that file as Python config
```

You can also load individual env vars:

```python
import os
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback")
```

### Prefixed Environment Variables

Flask 2.3 added `from_prefixed_env()` for bulk-loading env vars with a common prefix:

```python
app.config.from_prefixed_env()
# FLASK_SECRET_KEY -> app.config["SECRET_KEY"]
# FLASK_SQLALCHEMY_DATABASE_URI -> app.config["SQLALCHEMY_DATABASE_URI"]
```

The default prefix is `FLASK_`. Override with `app.config.from_prefixed_env("MYAPP")`.

## Configuration Classes

Organize config with inheritance:

```python
class Config:
    SECRET_KEY = "dev"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///dev.db"

class ProductionConfig(Config):
    SECRET_KEY = os.environ["SECRET_KEY"]
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
```

## Built-in Config Values

| Key | Default | Description |
|---|---|---|
| `DEBUG` | `False` | Enable debug mode |
| `TESTING` | `False` | Enable testing mode |
| `SECRET_KEY` | `None` | Used for session signing |
| `SESSION_COOKIE_NAME` | `"session"` | Name of the session cookie |
| `MAX_CONTENT_LENGTH` | `None` | Max request body size in bytes |
| `JSON_SORT_KEYS` | `True` | Sort JSON response keys |
| `JSONIFY_PRETTYPRINT_REGULAR` | `False` | Pretty-print JSON in non-debug |
| `PREFERRED_URL_SCHEME` | `"http"` | URL scheme for `url_for` |

## Instance Folder

For deployment-specific config that shouldn't be in version control:

```python
app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile("config.py")  # loads from instance/config.py
```

The instance folder is at `instance/` next to the application package.
