# Security Best Practices

**Source:** https://flask.palletsprojects.com/en/2.3.x/security/
**Fetched:** 2025-06-01

## Cross-Site Scripting (XSS)

Jinja2 auto-escapes all template variables by default:

```html
<!-- Safe: {{ user.name }} is escaped -->
<p>Hello, {{ user.name }}</p>

<!-- Dangerous: |safe disables escaping -->
<p>{{ user.bio | safe }}</p>
```

Never use `| safe` or `Markup()` on untrusted input.

## Cross-Site Request Forgery (CSRF)

Use Flask-WTF for CSRF protection:

```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
```

Include the token in forms:

```html
<form method="post">
    {{ form.csrf_token }}
    ...
</form>
```

For AJAX, set the token in a meta tag and send it as a header:

```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

## Secret Key

The `SECRET_KEY` is used for session signing and CSRF tokens. Always set a strong random key in production:

```python
import secrets
app.config["SECRET_KEY"] = secrets.token_hex(32)
```

Never commit the secret key to version control.

## Session Security

Flask sessions are signed cookies (not encrypted). Store only non-sensitive data in sessions.

```python
app.config["SESSION_COOKIE_SECURE"] = True     # HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True    # no JS access
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF protection
app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour
```

## Content Security Policy

Set CSP headers via `after_request`:

```python
@app.after_request
def set_csp(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

Or use Flask-Talisman:

```python
from flask_talisman import Talisman
Talisman(app, content_security_policy={"default-src": "'self'"})
```

## SQL Injection

Use parameterized queries — never interpolate user input into SQL:

```python
# SAFE
db.session.execute(db.text("SELECT * FROM user WHERE id = :id"), {"id": user_id})

# DANGEROUS — never do this
db.session.execute(f"SELECT * FROM user WHERE id = {user_id}")
```

SQLAlchemy's ORM methods (`.filter_by()`, `.filter()`) are safe by default.

## File Uploads

Validate and sanitize uploaded filenames:

```python
from werkzeug.utils import secure_filename

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files["file"]
    filename = secure_filename(f.filename)
    f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
```

Set `MAX_CONTENT_LENGTH` to limit upload size:

```python
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
```

## HTTPS

Always use HTTPS in production. Redirect HTTP to HTTPS:

```python
from flask_talisman import Talisman
Talisman(app, force_https=True)
```
