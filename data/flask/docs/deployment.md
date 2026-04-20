# Deployment Options

**Source:** https://flask.palletsprojects.com/en/2.3.x/deploying/
**Fetched:** 2025-06-01

## Production WSGI Servers

Never use `flask run` or `app.run()` in production. Use a production WSGI server:

### Gunicorn (recommended)

```bash
$ pip install gunicorn
$ gunicorn -w 4 -b 0.0.0.0:8000 "myapp:create_app()"
```

Options:
- `-w 4` — 4 worker processes (2–4× CPU cores)
- `-b 0.0.0.0:8000` — bind address
- `--timeout 120` — worker timeout
- `--access-logfile -` — log to stdout

### Waitress (Windows-compatible)

```bash
$ pip install waitress
$ waitress-serve --port=8080 --call "myapp:create_app"
```

### uWSGI

```bash
$ uwsgi --http 0.0.0.0:8000 --master -p 4 -w myapp:app
```

## Application Factories

Production deployments should use the factory pattern:

```python
# myapp/__init__.py
def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY="prod-key")
    if config:
        app.config.from_mapping(config)

    from . import auth, blog
    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)

    return app
```

WSGI entry point:

```python
# wsgi.py
from myapp import create_app

app = create_app()
```

## Reverse Proxy

Behind nginx or Apache, configure `ProxyFix`:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

## Environment Variables

Use environment variables for secrets:

```bash
export FLASK_SECRET_KEY="actual-secret"
export FLASK_SQLALCHEMY_DATABASE_URI="postgresql://..."
```

Load with:

```python
app.config.from_prefixed_env()
```

## Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "myapp:create_app()"]
```

## Static Files in Production

In production, serve static files through nginx or a CDN — not through Flask. Configure nginx:

```nginx
location /static {
    alias /var/www/myapp/static;
}
```
