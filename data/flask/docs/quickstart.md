# Quickstart — Minimal Application and Routing

**Source:** https://flask.palletsprojects.com/en/2.3.x/quickstart/
**Fetched:** 2025-06-01

## A Minimal Application

```python
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"
```

Save this as `hello.py`, then run:

```bash
$ flask --app hello run
 * Serving Flask app 'hello'
 * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

## What `Flask(__name__)` Does

The `__name__` argument tells Flask where to look for resources (templates, static files). For a single module, `__name__` is always correct. For a package, you may need to hardcode the import name.

## Routing

Use the `@app.route()` decorator to bind a URL to a function:

```python
@app.route("/")
def index():
    return "Index Page"

@app.route("/hello")
def hello():
    return "Hello, World"
```

### Variable Rules

```python
@app.route("/user/<username>")
def show_user_profile(username):
    return f"User {username}"

@app.route("/post/<int:post_id>")
def show_post(post_id):
    return f"Post {post_id}"
```

Converter types: `string` (default), `int`, `float`, `path`, `uuid`.

### HTTP Methods

```python
from flask import request

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return do_the_login()
    else:
        return show_the_login_form()
```

## Static Files

Static files are served from the `static/` folder:

```python
url_for("static", filename="style.css")
```

## Rendering Templates

Flask uses Jinja2 for templating:

```python
from flask import render_template

@app.route("/hello/<name>")
def hello(name=None):
    return render_template("hello.html", name=name)
```

Templates live in the `templates/` folder next to your module.

## Debug Mode

Run with debug mode for auto-reloading and the interactive debugger:

```bash
$ flask --app hello run --debug
```

**Warning:** Never run the development server in production. Use a production WSGI server (Gunicorn, Waitress) instead.

## URL Building

Use `url_for()` to build URLs for a specific function:

```python
from flask import url_for

with app.test_request_context():
    print(url_for("index"))          # /
    print(url_for("hello"))          # /hello
    print(url_for("show_user_profile", username="John"))  # /user/John
```
