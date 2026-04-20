# Database Integration Patterns

**Source:** https://flask.palletsprojects.com/en/2.3.x/patterns/sqlite3/ + /patterns/sqlalchemy/
**Fetched:** 2025-06-01

## Flask-SQLAlchemy Setup

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app
```

## Defining Models

```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship("Post", backref="author", lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
```

## Creating Tables

```python
with app.app_context():
    db.create_all()
```

## CRUD Operations

```python
# Create
user = User(username="alice", email="alice@example.com")
db.session.add(user)
db.session.commit()

# Read
user = User.query.filter_by(username="alice").first()
users = User.query.all()
user = User.query.get(1)  # by primary key

# Update
user.email = "new@example.com"
db.session.commit()

# Delete
db.session.delete(user)
db.session.commit()
```

## Query API

```python
# Filtering
User.query.filter(User.username.like("%alice%")).all()
User.query.filter(User.id > 5).order_by(User.username).limit(10).all()

# Pagination
page = User.query.paginate(page=1, per_page=20, error_out=False)
```

## Session Management

Flask-SQLAlchemy automatically manages sessions per request. The session is scoped to the application context and removed at the end of each request via `teardown_appcontext`.

```python
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()
```

## Raw SQL

```python
result = db.session.execute(db.text("SELECT * FROM user WHERE id = :id"), {"id": 1})
```

## Migrations with Flask-Migrate

```bash
$ flask db init           # create migrations directory
$ flask db migrate -m "add users table"
$ flask db upgrade        # apply migration
$ flask db downgrade      # revert last migration
```

## Multiple Databases

```python
app.config["SQLALCHEMY_BINDS"] = {
    "users": "sqlite:///users.db",
    "posts": "sqlite:///posts.db",
}

class User(db.Model):
    __bind_key__ = "users"
    id = db.Column(db.Integer, primary_key=True)
```

## Connection Pooling

SQLAlchemy manages a connection pool by default. Key settings:

```python
app.config["SQLALCHEMY_POOL_SIZE"] = 10
app.config["SQLALCHEMY_POOL_TIMEOUT"] = 20
app.config["SQLALCHEMY_MAX_OVERFLOW"] = 5
```
