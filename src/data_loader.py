"""Load handbook markdown + synthetic Slack threads + test questions into a uniform schema."""
from __future__ import annotations
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = ROOT / "data" / "handbook"
SLACK_FILE = ROOT / "data" / "slack.json"
QUESTIONS_FILE = ROOT / "data" / "test_questions.json"


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
            },
        })
    return docs


def load_slack() -> list[dict]:
    if not SLACK_FILE.exists():
        return []
    return json.loads(SLACK_FILE.read_text(encoding="utf-8"))


def load_questions() -> list[dict]:
    if not QUESTIONS_FILE.exists():
        return []
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def load_all_docs() -> list[dict]:
    return load_handbook() + load_slack()


if __name__ == "__main__":
    hb = load_handbook()
    sl = load_slack()
    q = load_questions()
    print(f"handbook: {len(hb)} docs")
    print(f"slack:    {len(sl)} threads")
    print(f"questions:{len(q)}")
    for d in hb:
        print(f"  {d['id']}: {d['metadata']['title']} ({len(d['content'])} chars)")
    for d in sl:
        rel = d["metadata"].get("relationship", "?")
        print(f"  {d['id']}: [{rel}] {d['metadata']['title']}")
