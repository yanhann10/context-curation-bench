# Async Views and Background Tasks

**Source:** https://flask.palletsprojects.com/en/2.3.x/async-await/
**Fetched:** 2025-06-01

## Async Views (Flask 2.0+)

Flask 2.0 added support for `async def` view functions. Install the `async` extra:

```bash
pip install "flask[async]"
```

Then define async views:

```python
@app.route("/data")
async def get_data():
    data = await fetch_data_from_api()
    return jsonify(data)
```

## How It Works

Flask runs async views using `asyncio.run()` in a separate thread. This means:
- Each async view gets its own event loop
- You CAN use `await` inside the view
- You CANNOT share event loops across requests
- Async views run in a thread executor, not a native async server

**Important:** Flask's async support is a compatibility layer, not native ASGI. For high-concurrency async workloads, consider Quart (Flask's ASGI counterpart) or FastAPI.

## Async Hooks

Request hooks can also be async:

```python
@app.before_request
async def load_user():
    g.user = await get_user_from_db()

@app.after_request
async def log_response(response):
    await log_to_service(response.status_code)
    return response
```

## Background Tasks

For background work, use a task queue like Celery or RQ:

```python
from celery import Celery

celery = Celery("myapp", broker="redis://localhost:6379/0")

@celery.task
def send_email(to, subject, body):
    # send email logic
    pass

@app.route("/send-email", methods=["POST"])
def trigger_email():
    send_email.delay(
        to=request.form["to"],
        subject=request.form["subject"],
        body=request.form["body"],
    )
    return jsonify(status="queued")
```

## When to Use Async

Use async views when:
- Making multiple external API calls that can run concurrently
- I/O-bound operations where you can `await` multiple tasks

Don't use async views when:
- CPU-bound work (use a task queue instead)
- Simple database queries (synchronous is fine)
- You need to share state across the event loop

## Async and Extensions

Most Flask extensions (Flask-SQLAlchemy, Flask-Login) are synchronous. Using them inside an `async def` view works but blocks the event loop. For true async database access, use `databases` or `encode/databases` with async views.

## Quart: Flask's ASGI Sibling

Quart is API-compatible with Flask but runs natively on ASGI (via Hypercorn or uvicorn). Migration from Flask is straightforward — most `from flask import X` becomes `from quart import X`.
