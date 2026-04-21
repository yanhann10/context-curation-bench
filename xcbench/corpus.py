"""Typed CorpusSpec: a first-class corpus abstraction.

Each `Doc` carries `kind` (static | fresh), a `timestamp`, and a
`freshness_priority` (higher = prefer this source when entries conflict).
Strategies can filter/order by these fields — letta-evals has no analog.

A `CorpusSpec` is a collection of Docs plus a named slice map
(e.g. {"handbook": [...ids...], "slack": [...ids...]}) so questions can
reference a slice by name without hard-coding ids.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .registry import corpus_loader

DocKind = Literal["static", "fresh"]


@dataclass
class Doc:
    id: str
    kind: DocKind
    content: str
    title: str = ""
    source: str = ""
    timestamp: str = ""
    freshness_priority: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def metadata(self) -> dict:
        m = {"title": self.title, "source": self.source, "timestamp": self.timestamp}
        m.update(self.extra)
        return m

    def as_legacy_dict(self) -> dict:
        """Shape used by existing src/strategies*.py (type='static'|'slack')."""
        legacy_type = "static" if self.kind == "static" else "slack"
        return {
            "id": self.id,
            "type": legacy_type,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class CorpusSpec:
    docs: list[Doc]
    slices: dict[str, list[str]] = field(default_factory=dict)

    def by_kind(self, kind: DocKind) -> list[Doc]:
        return [d for d in self.docs if d.kind == kind]

    def slice(self, name: str) -> list[Doc]:
        ids = set(self.slices.get(name, []))
        return [d for d in self.docs if d.id in ids]

    def scoped(self, doc_ids: list[str]) -> "CorpusSpec":
        """Return a new CorpusSpec containing only the listed doc IDs."""
        id_set = set(doc_ids)
        return CorpusSpec(
            docs=[d for d in self.docs if d.id in id_set],
            slices={k: [i for i in v if i in id_set] for k, v in self.slices.items()},
        )

    def as_legacy_list(self) -> list[dict]:
        return [d.as_legacy_dict() for d in self.docs]


@corpus_loader("jsonl")
def load_jsonl(path: str) -> CorpusSpec:
    """Load a JSONL corpus file. Each line:

      {"id": "...", "kind": "static"|"fresh", "content": "...",
       "title": "...", "source": "...", "timestamp": "...",
       "freshness_priority": 0, "slices": ["handbook"]}
    """
    p = Path(path)
    docs: list[Doc] = []
    slices: dict[str, list[str]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        slice_names = row.pop("slices", [])
        d = Doc(
            id=row["id"],
            kind=row["kind"],
            content=row["content"],
            title=row.get("title", ""),
            source=row.get("source", ""),
            timestamp=row.get("timestamp", ""),
            freshness_priority=int(row.get("freshness_priority", 0)),
            extra=row.get("extra", {}),
        )
        docs.append(d)
        for s in slice_names:
            slices.setdefault(s, []).append(d.id)
    return CorpusSpec(docs=docs, slices=slices)
