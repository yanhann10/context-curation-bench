"""One-shot: convert legacy data/ layout into ccbench JSONL format.

  data/handbook/*.md + data/slack_api.json  ->  data/corpus.jsonl
  data/test_questions_v2.json               ->  data/questions.jsonl

Run:
  python -m ccbench.convert_data
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = ROOT / "data" / "handbook"
SLACK_API = ROOT / "data" / "slack_api.json"
QUESTIONS_V2 = ROOT / "data" / "test_questions_v2.json"
CORPUS_OUT = ROOT / "data" / "corpus.jsonl"
QUESTIONS_OUT = ROOT / "data" / "questions.jsonl"

HANDBOOK_TS = "2026-01-01T00:00:00Z"


def main() -> int:
    corpus_rows: list[dict] = []

    for path in sorted(HANDBOOK_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        text = path.read_text(encoding="utf-8")
        title = text.split("\n", 1)[0].lstrip("# ").strip() or path.stem
        corpus_rows.append({
            "id": f"handbook/{path.stem}",
            "kind": "static",
            "title": title,
            "source": "gitlab-handbook",
            "timestamp": HANDBOOK_TS,
            "freshness_priority": 0,
            "slices": ["handbook"],
            "content": text,
        })

    if SLACK_API.exists():
        for row in json.loads(SLACK_API.read_text(encoding="utf-8")):
            meta = row.get("metadata", {})
            corpus_rows.append({
                "id": row["id"],
                "kind": "fresh",
                "title": meta.get("title", row["id"]),
                "source": meta.get("source", "slack"),
                "timestamp": meta.get("timestamp", ""),
                "freshness_priority": 10,
                "slices": ["slack"],
                "content": row["content"],
                "extra": {k: v for k, v in meta.items()
                          if k not in ("title", "source", "timestamp")},
            })

    CORPUS_OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in corpus_rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {CORPUS_OUT}  ({len(corpus_rows)} docs)")

    q_rows: list[dict] = []
    if QUESTIONS_V2.exists():
        for row in json.loads(QUESTIONS_V2.read_text(encoding="utf-8")):
            q_rows.append({
                "id": row["id"],
                "input": row["question"],
                "golden": row["golden_answer"],
                "category": row.get("category", ""),
                "key_facts": row.get("key_facts", []),
                "relevant_doc_ids": row.get("relevant_source_ids", []),
                "relevant_slices": (
                    ["handbook"] if row.get("category") == "portal_only"
                    else ["slack"] if row.get("category") == "slack_only"
                    else ["handbook", "slack"]
                ),
            })
    QUESTIONS_OUT.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in q_rows) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {QUESTIONS_OUT}  ({len(q_rows)} questions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
