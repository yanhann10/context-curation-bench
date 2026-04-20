"""Load handbook markdown + Slack threads + test questions into a uniform schema.

Handbook docs get a synthetic source_timestamp of 2026-01-01 so strategies
can compare recency against (newer) Slack threads uniformly.
"""
from __future__ import annotations
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = ROOT / "data" / "handbook"
SLACK_FILE = ROOT / "data" / "slack.json"
SLACK_API_FILE = ROOT / "data" / "slack_api.json"
QUESTIONS_FILE = ROOT / "data" / "test_questions.json"
QUESTIONS_V2_FILE = ROOT / "data" / "test_questions_v2.json"

# Polars domain
POLARS_DIR = ROOT / "data" / "polars"
POLARS_DOCS_DIR = POLARS_DIR / "docs"
POLARS_SLACK_FILE = POLARS_DIR / "slack_api.json"
POLARS_QUESTIONS_FILE = POLARS_DIR / "test_questions.json"

# All handbook docs share this synthetic source date — strategies that are
# recency-aware will compare it against Slack thread timestamps.
HANDBOOK_SOURCE_TIMESTAMP = "2026-01-01T00:00:00Z"


def load_handbook() -> list[dict]:
    docs = []
    for path in sorted(HANDBOOK_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        text = path.read_text(encoding="utf-8")
        title = text.split("\n", 1)[0].lstrip("# ").strip() or path.stem
        docs.append({
            "id": f"handbook/{path.stem}",
            "type": "static",
            "content": text,
            "metadata": {
                "title": title,
                "source": "gitlab-handbook",
                "path": str(path.relative_to(ROOT)),
                "timestamp": HANDBOOK_SOURCE_TIMESTAMP,
            },
        })
    return docs


def load_slack(path: Path = SLACK_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_slack_api() -> list[dict]:
    """Load Slack-API-shape threads (richer metadata: channel_id, thread_ts,
    user_id, reactions, validated_by_hr). Uses same internal schema."""
    return load_slack(SLACK_API_FILE)


def load_questions(path: Path = QUESTIONS_FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_questions_v2() -> list[dict]:
    return load_questions(QUESTIONS_V2_FILE)


def load_all_docs(slack_source: str = "simple") -> list[dict]:
    """slack_source='simple' uses slack.json (v1); 'api' uses slack_api.json (v2)."""
    if slack_source == "api":
        return load_handbook() + load_slack_api()
    return load_handbook() + load_slack()


# ---------- Polars domain ----------

def load_polars_docs() -> list[dict]:
    """Load 12-13 Polars user-guide markdown pages. Uniform source_timestamp=2026-01-01."""
    docs = []
    for path in sorted(POLARS_DOCS_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        text = path.read_text(encoding="utf-8")
        title = text.split("\n", 1)[0].lstrip("# ").strip() or path.stem
        docs.append({
            "id": f"polars-docs/{path.stem}",
            "type": "static",
            "content": text,
            "metadata": {
                "title": title,
                "source": "polars-docs",
                "path": str(path.relative_to(ROOT)),
                "timestamp": HANDBOOK_SOURCE_TIMESTAMP,
            },
        })
    return docs


def load_polars_slack() -> list[dict]:
    """Load 10 GitHub-discussion-shaped threads (Slack-API schema)."""
    return load_slack(POLARS_SLACK_FILE)


def load_polars_questions() -> list[dict]:
    return load_questions(POLARS_QUESTIONS_FILE)


def load_polars_all() -> list[dict]:
    return load_polars_docs() + load_polars_slack()


if __name__ == "__main__":
    for label, docs, qs in [
        ("simple (v1)", load_all_docs("simple"), load_questions()),
        ("api    (v2)", load_all_docs("api"), load_questions_v2()),
    ]:
        s = sum(1 for d in docs if d["type"] == "static")
        sl = sum(1 for d in docs if d["type"] == "slack")
        print(f"{label}: {s} static, {sl} slack, {len(qs)} questions")
