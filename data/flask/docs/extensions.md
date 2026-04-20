# Flask Extensions Ecosystem

**Source:** https://flask.palletsprojects.com/en/2.3.x/extensions/
**Fetched:** 2025-06-01

## What Are Extensions?

Flask extensions add functionality to your application — database access, authentication, API tooling, etc. They follow the naming convention `Flask-Foo` (package) / `flask_foo` (import).

## Finding Extensions

The official Flask extension registry is at https://flask.palletsprojects.com/en/2.3.x/extensions/. Community extensions are on PyPI — search for `flask-*`.

## Installing Extensions

```bash
pip install Flask-SQLAlchemy
pip install Flask-Login
pip install Flask-WTF
```

## Common Extension Pattern

Most extensions follow the init-app pattern:

```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    db.init_app(app)
    return app
```

## Popular Extensions

### Flask-SQLAlchemy (Database ORM)

```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

# Create tables
with app.app_context():
    db.create_all()
```

### Flask-Login (User Sessions)

```python
from flask_login import LoginManager, login_user, login_required

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")
```

### Flask-WTF (Forms + CSRF)

```python
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
```

### Flask-Migrate (Database Migrations)

```python
from flask_migrate import Migrate

migrate = Migrate(app, db)
```

```bash
$ flask db init
$ flask db migrate -m "Initial migration"
$ flask db upgrade
```

### Flask-RESTful (REST API)

```python
from flask_restful import Api, Resource

api = Api(app)

class UserResource(Resource):
    def get(self, user_id):
        user = User.query.get_or_404(user_id)
        return {"id": user.id, "name": user.username}

api.add_resource(UserResource, "/api/users/<int:user_id>")
```

## Writing Your Own Extension

```python
class MyExtension:
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.config.setdefault("MY_SETTING", "default")
        app.extensions["my_extension"] = self
```

## Deprecated: flask.ext

The old `from flask.ext.foo import Foo` import style was removed in Flask 1.0. Always use `from flask_foo import Foo`.
