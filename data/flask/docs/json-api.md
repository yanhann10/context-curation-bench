# JSON APIs and Responses

**Source:** https://flask.palletsprojects.com/en/2.3.x/patterns/api/
**Fetched:** 2025-06-01

## jsonify

The `jsonify` function creates a JSON response with the correct `Content-Type` header:

```python
from flask import jsonify

@app.route("/api/users")
def get_users():
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return jsonify(users)
```

`jsonify` accepts dicts, lists, or keyword arguments:

```python
return jsonify(name="Alice", age=30)
# Returns: {"age": 30, "name": "Alice"}
```

## Returning JSON Directly

Since Flask 2.2, you can return a dict directly from a view function — Flask calls `jsonify` automatically:

```python
@app.route("/api/user/<int:id>")
def get_user(id):
    user = User.query.get_or_404(id)
    return {"id": user.id, "name": user.name}
```

## Request JSON

Access JSON data from a request:

```python
from flask import request

@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json()
    # data is a Python dict
    name = data["name"]
    return jsonify(id=new_id, name=name), 201
```

`request.json` is a shortcut for `request.get_json()`. Both return `None` if the content type isn't JSON (use `force=True` to parse anyway).

## Custom JSON Encoder

Override the default JSON encoder for custom types:

```python
from flask.json import JSONEncoder
import datetime

class CustomEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)

app.json_encoder = CustomEncoder
```

## JSON Error Responses

Return JSON error responses for API endpoints:

```python
@app.errorhandler(400)
def bad_request(e):
    return jsonify(error="Bad Request", message=str(e)), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Not Found"), 404
```

## Content Negotiation

Check what the client accepts:

```python
from flask import request

@app.errorhandler(404)
def not_found(e):
    if request.accept_mimetypes.accept_json:
        return jsonify(error="Not Found"), 404
    return render_template("404.html"), 404
```

## CORS

For cross-origin API access, use `flask-cors`:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

## JSON_SORT_KEYS

By default, `JSON_SORT_KEYS = True` sorts JSON output keys alphabetically for deterministic output. Set to `False` for faster serialization in production.

## flask.json Module

The `flask.json` module provides `dumps`, `loads`, `jsonify`, and the encoder/decoder classes. These are wrappers around the standard library `json` module with Flask-specific defaults (like the custom encoder).
