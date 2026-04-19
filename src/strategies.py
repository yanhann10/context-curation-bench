"""Context curation strategies for Stage 1.

- full_context: stuff everything
- meta_harness_optimized: apply a CurationSpec produced by harness_optimizer
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


Ordering = Literal["as_is", "static_first", "slack_first", "recency_first"]
DocFormat = Literal["raw", "titled", "structured"]


@dataclass
class CurationSpec:
    """Structured configuration that the optimizer evolves.

    This replaces 'evolve arbitrary Python code' (what real Meta-Harness does)
    with 'evolve a small typed configuration'. Same loop, safer to execute,
    easier to interpret. Trade-off called out in the README.
    """
    include_static_ids: list[str] = field(default_factory=list)
    include_slack_ids: list[str] = field(default_factory=list)
    ordering: Ordering = "static_first"
    doc_format: DocFormat = "titled"
    prepend_instructions: str = ""
    max_chars_per_doc: int = 4000

    def describe(self) -> str:
        return (
            f"CurationSpec(static={len(self.include_static_ids)}, "
            f"slack={len(self.include_slack_ids)}, ordering={self.ordering}, "
            f"format={self.doc_format}, max_chars/doc={self.max_chars_per_doc})"
        )


def _format_doc(doc: dict, fmt: DocFormat, max_chars: int) -> str:
    body = doc["content"]
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...[truncated]"
    title = doc["metadata"].get("title", doc["id"])
    src = doc["metadata"].get("source", "unknown")
    ts = doc["metadata"].get("timestamp", "")
    if fmt == "raw":
        return body
    if fmt == "titled":
        header = f"--- {title} [{src}{(' @ ' + ts) if ts else ''}] ---"
        return f"{header}\n{body}"
    # structured
    return (
        f"<doc id='{doc['id']}' source='{src}'"
        f"{(' timestamp=' + chr(39) + ts + chr(39)) if ts else ''}>\n"
        f"<title>{title}</title>\n{body}\n</doc>"
    )


def _sort_docs(docs: list[dict], ordering: Ordering) -> list[dict]:
    if ordering == "as_is":
        return list(docs)
    if ordering == "static_first":
        return sorted(docs, key=lambda d: (d["type"] != "static", d["id"]))
    if ordering == "slack_first":
        return sorted(docs, key=lambda d: (d["type"] != "slack", d["id"]))
    if ordering == "recency_first":
        def key(d):
            ts = d["metadata"].get("timestamp", "")
            return (ts == "", -len(ts), ts)
        return sorted(docs, key=key, reverse=True)
    return list(docs)


def full_context(question: str, docs: list[dict]) -> str:
    """Strategy 1: stuff everything. Static docs first, then Slack."""
    ordered = _sort_docs(docs, "static_first")
    parts = [_format_doc(d, "titled", max_chars=10_000) for d in ordered]
    body = "\n\n".join(parts)
    return (
        "Answer the user's question using ONLY the sources below. If the sources disagree, "
        "prefer the most recent. Cite source titles in square brackets. "
        "Do NOT refuse based on domain assumptions — use the sources regardless of what the topic sounds like.\n\n"
        f"=== SOURCES ===\n{body}\n\n=== QUESTION ===\n{question}"
    )


def meta_harness_optimized(question: str, docs: list[dict], spec: CurationSpec) -> str:
    """Strategy 2: apply a CurationSpec to produce the prompt."""
    selected: list[dict] = []
    if spec.include_static_ids:
        by_id = {d["id"]: d for d in docs if d["type"] == "static"}
        for did in spec.include_static_ids:
            if did in by_id:
                selected.append(by_id[did])
    else:
        selected.extend([d for d in docs if d["type"] == "static"])
    if spec.include_slack_ids:
        by_id = {d["id"]: d for d in docs if d["type"] == "slack"}
        for did in spec.include_slack_ids:
            if did in by_id:
                selected.append(by_id[did])
    else:
        selected.extend([d for d in docs if d["type"] == "slack"])

    ordered = _sort_docs(selected, spec.ordering)
    parts = [_format_doc(d, spec.doc_format, spec.max_chars_per_doc) for d in ordered]
    body = "\n\n".join(parts)

    instructions = (
        spec.prepend_instructions
        or "Answer using ONLY the provided sources. Prefer the most recent info when sources disagree. Do NOT refuse based on domain assumptions."
    )
    return (
        f"{instructions}\n\n"
        f"=== SOURCES ({len(ordered)} included) ===\n{body}\n\n"
        f"=== QUESTION ===\n{question}"
    )
