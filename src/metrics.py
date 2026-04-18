"""String-overlap QA metrics — SQuAD-style F1 + Exact Match.

Text is normalized (lowercase, strip punctuation, collapse whitespace, drop
articles) before comparison. Computed token-level.
"""
from __future__ import annotations
import re
import string
from collections import Counter


_ARTICLES = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_PUNCT = re.compile(f"[{re.escape(string.punctuation)}]")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    if text is None:
        return ""
    t = text.lower()
    t = _PUNCT.sub(" ", t)
    t = _ARTICLES.sub(" ", t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def exact_match(pred: str, gold: str) -> float:
    return 1.0 if normalize(pred) == normalize(gold) else 0.0


def f1(pred: str, gold: str) -> float:
    p = tokens(pred)
    g = tokens(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    common = Counter(p) & Counter(g)
    n_common = sum(common.values())
    if n_common == 0:
        return 0.0
    precision = n_common / len(p)
    recall = n_common / len(g)
    return 2 * precision * recall / (precision + recall)


def f1_against_any(pred: str, golds: list[str]) -> float:
    """Max F1 across a list of acceptable golden answers."""
    if not golds:
        return 0.0
    return max(f1(pred, g) for g in golds)


def em_against_any(pred: str, golds: list[str]) -> float:
    if not golds:
        return 0.0
    return max(exact_match(pred, g) for g in golds)


def key_facts_recall(pred: str, key_facts: list[str]) -> float:
    """Fraction of key_facts whose normalized form appears in the prediction."""
    if not key_facts:
        return 1.0
    norm_pred = normalize(pred)
    hits = sum(1 for fact in key_facts if normalize(fact) in norm_pred)
    return hits / len(key_facts)
