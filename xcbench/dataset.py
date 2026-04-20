"""Question dataset loader. JSONL, one question per line.

Each row may include adjudication metadata in addition to the original fields:
  {"id": "...", "input": "...", "golden": "...", "category": "...",
   "key_facts": ["..."], "relevant_slices": ["handbook", "slack"],
   "relevant_doc_ids": ["..."],
   "gold_status": "resolved|scoped|ambiguous",
   "acceptable_answers": ["..."],
   "abstain_expected": false,
   "canonical_source_ids": ["..."],
   "authority_rule_used": "...",
   "adjudication_rationale": "...",
   "scope_conditions": ["..."]}
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_GOLD_STATUS = {"resolved", "scoped", "ambiguous"}


@dataclass
class Question:
    id: str
    input: str
    golden: str
    category: str = ""
    key_facts: list[str] = field(default_factory=list)
    relevant_slices: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)
    gold_status: str = "resolved"
    acceptable_answers: list[str] = field(default_factory=list)
    abstain_expected: bool = False
    canonical_source_ids: list[str] = field(default_factory=list)
    authority_rule_used: str = ""
    adjudication_rationale: str = ""
    scope_conditions: list[str] = field(default_factory=list)

    def evaluation_golds(self) -> list[str]:
        golds: list[str] = []
        for text in [self.golden, *self.acceptable_answers]:
            t = (text or "").strip()
            if t and t not in golds:
                golds.append(t)
        return golds

    def as_legacy_dict(self) -> dict:
        """Shape used by existing src/evaluator*.py."""
        return {
            "id": self.id,
            "question": self.input,
            "golden_answer": self.golden,
            "acceptable_answers": self.acceptable_answers,
            "category": self.category,
            "key_facts": self.key_facts,
            "relevant_source_ids": self.relevant_doc_ids,
            "gold_status": self.gold_status,
            "abstain_expected": self.abstain_expected,
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
            gold_status=row.get("gold_status", "resolved"),
            acceptable_answers=list(row.get("acceptable_answers", [])),
            abstain_expected=bool(row.get("abstain_expected", False)),
            canonical_source_ids=list(row.get("canonical_source_ids", [])),
            authority_rule_used=row.get("authority_rule_used", ""),
            adjudication_rationale=row.get("adjudication_rationale", ""),
            scope_conditions=list(row.get("scope_conditions", [])),
        ))
    return out


def validate_questions(questions: list[Question]) -> list[str]:
    errs: list[str] = []
    for q in questions:
        if q.gold_status not in ALLOWED_GOLD_STATUS:
            errs.append(
                f"{q.id}: gold_status='{q.gold_status}' not in {sorted(ALLOWED_GOLD_STATUS)}"
            )
        if not q.evaluation_golds():
            errs.append(f"{q.id}: no golden or acceptable_answers provided")
        if q.abstain_expected and q.gold_status != "ambiguous":
            errs.append(f"{q.id}: abstain_expected=true requires gold_status='ambiguous'")
        if q.gold_status == "ambiguous" and not q.abstain_expected:
            errs.append(f"{q.id}: gold_status='ambiguous' requires abstain_expected=true")
        if q.gold_status in {"resolved", "scoped"} and not q.canonical_source_ids:
            errs.append(f"{q.id}: gold_status='{q.gold_status}' requires canonical_source_ids")
        if q.gold_status == "scoped" and not q.scope_conditions:
            errs.append(f"{q.id}: gold_status='scoped' requires scope_conditions")
        if q.relevant_doc_ids:
            missing = sorted(set(q.canonical_source_ids) - set(q.relevant_doc_ids))
            if missing:
                errs.append(
                    f"{q.id}: canonical_source_ids must be subset of relevant_doc_ids; extra={missing}"
                )
    return errs
