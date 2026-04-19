"""Question dataset loader. JSONL, one question per line.

Each row:
  {"id": "...", "input": "...", "golden": "...", "category": "...",
   "key_facts": ["..."], "relevant_slices": ["handbook", "slack"],
   "relevant_doc_ids": ["..."]}
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Question:
    id: str
    input: str
    golden: str
    category: str = ""
    key_facts: list[str] = field(default_factory=list)
    relevant_slices: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)

    def as_legacy_dict(self) -> dict:
        """Shape used by existing src/evaluator*.py."""
        return {
            "id": self.id,
            "question": self.input,
            "golden_answer": self.golden,
            "category": self.category,
            "key_facts": self.key_facts,
            "relevant_source_ids": self.relevant_doc_ids,
        }


def load_questions(path: str) -> list[Question]:
    out: list[Question] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        out.append(Question(
            id=row["id"],
            input=row.get("input", row.get("question", "")),
            golden=row.get("golden", row.get("golden_answer", "")),
            category=row.get("category", ""),
            key_facts=list(row.get("key_facts", [])),
            relevant_slices=list(row.get("relevant_slices", [])),
            relevant_doc_ids=list(row.get("relevant_doc_ids", row.get("relevant_source_ids", []))),
        ))
    return out
